"""Dew point source scanning for water temperature control.

Enumerates every humidity source that constrains how cold the cooling supply
water may run, pairs each with a co-located temperature, smooths the humidity,
applies plausibility/staleness guards, and returns the worst (highest) dew
point.  Reads only ``hass.states`` and the coordinator's zone registry — it
never reaches into thermostat entity internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import math
from typing import TYPE_CHECKING, Any

from ..const import (
    DEFAULT_WATER_TEMP_DEW_POINT_MARGIN,
    WATER_TEMP_AIR_TEMP_MAX,
    WATER_TEMP_AIR_TEMP_MIN,
    WATER_TEMP_BLIND_MIN_SUPPLY,
    WATER_TEMP_EMA_WINDOW_MINUTES,
    WATER_TEMP_RH_MAX,
    WATER_TEMP_RH_MIN,
    WATER_TEMP_STALE_MINUTES,
    WATER_TEMP_WARN_INTERVAL_SECONDS,
)
from ..helpers.dew_point import dew_point

try:
    from homeassistant.components.climate import HVACMode
    from homeassistant.helpers import entity_registry as er
except ImportError:  # pragma: no cover - test environment without full HA
    HVACMode = None  # type: ignore[assignment] - HA boundary stub for no-HA test runs
    er = None  # type: ignore[assignment] - HA boundary stub for no-HA test runs

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..coordinator import AdaptiveThermostatCoordinator

_LOGGER = logging.getLogger(__name__)

_COOL_MODE = "cool"

TEMP_SOURCE_DEVICE = "device"
TEMP_SOURCE_CLIMATE = "climate"
TEMP_SOURCE_ENTITY = "entity"


@dataclass(frozen=True)
class SourceReading:
    """One resolved humidity source and its computed dew point."""

    key: str
    rh_pct: float
    temp_c: float
    dew_point_c: float
    real: bool
    temp_source: str


@dataclass(frozen=True)
class DewPointScan:
    """Result of one full scan across all sources."""

    dew_point: float | None
    worst_source: str | None
    blind: bool
    readings: tuple[SourceReading, ...]


class DewPointScanner:
    """Scan zones and extra sensor pairs for the worst-case indoor dew point."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: AdaptiveThermostatCoordinator,
        extra_sensors: list[dict[str, str]],
        fallback_humidity: float,
        dew_point_margin: float = DEFAULT_WATER_TEMP_DEW_POINT_MARGIN,
        ema_window_minutes: float = WATER_TEMP_EMA_WINDOW_MINUTES,
        stale_after_minutes: float = WATER_TEMP_STALE_MINUTES,
    ) -> None:
        """Initialize the scanner.

        Args:
            hass: Home Assistant instance.
            coordinator: Zone registry, used for COOL-mode zones and zone temps.
            extra_sensors: List of ``{"humidity": ..., "temperature": ...}`` pairs.
            fallback_humidity: RH in % used when a source has no usable reading.
            dew_point_margin: The caller's ``dew_point_margin``, needed only so
                :meth:`blind_zone_reading` can express its floor as a dew point
                (the caller adds the margin back on).
            ema_window_minutes: Time constant of the per-source RH EMA.
            stale_after_minutes: ``state.last_updated`` age past which RH is stale.
        """
        self._hass = hass
        self._coordinator = coordinator
        self._extra_sensors = extra_sensors
        self._fallback_humidity = fallback_humidity
        self._dew_point_margin = dew_point_margin
        self._ema_window_minutes = ema_window_minutes
        self._stale_after_minutes = stale_after_minutes

        self._ema: dict[str, float] = {}
        self._ema_updated: dict[str, datetime] = {}
        self._temp_source_logged: set[str] = set()
        self._last_warned: dict[str, datetime] = {}

    # ── public API ───────────────────────────────────────────────────────────

    def scan(self, now: datetime) -> DewPointScan:
        """Scan every source and return the worst-case dew point.

        Args:
            now: Current wall-clock time (``dt_util.utcnow()`` from the caller).

        Returns:
            A :class:`DewPointScan`.  ``blind`` is True when no source produced
            a plausible, fresh reading — the caller must then floor the supply
            temperature conservatively.
        """
        readings: list[SourceReading] = []
        readings.extend(self._scan_zones(now))
        readings.extend(self._scan_extra_sensors(now))

        if not readings:
            self._warn_once("no_sources", "Water temp control: no dew point sources available")
            return DewPointScan(dew_point=None, worst_source=None, blind=True, readings=())

        worst = max(readings, key=lambda reading: reading.dew_point_c)
        blind = not any(reading.real for reading in readings)
        if blind:
            self._warn_once(
                "blind",
                "Water temp control: no plausible, fresh humidity reading from any source — "
                "running blind on fallback humidity",
            )

        return DewPointScan(
            dew_point=worst.dew_point_c,
            worst_source=worst.key,
            blind=blind,
            readings=tuple(readings),
        )

    # ── source enumeration ───────────────────────────────────────────────────

    def _scan_zones(self, now: datetime) -> list[SourceReading]:
        """Build readings for every eligible COOL-mode zone."""
        readings: list[SourceReading] = []
        cool_mode = HVACMode.COOL if HVACMode is not None else _COOL_MODE

        for zone_id, zone_data in self._coordinator.get_zones_in_mode(cool_mode).items():
            humidity_entity_id = zone_data.get("humidity_sensor")
            if not humidity_entity_id:
                continue
            if zone_data.get("exclude_from_dew_point"):
                continue
            if self._zone_humidity_paused(zone_data):
                continue

            temp_c, temp_source, unresolvable = self._resolve_zone_temperature(zone_id, humidity_entity_id)
            if temp_c is None:
                if unresolvable:
                    # Review finding #8: a registered COOL zone's derived
                    # climate_entity_id (or its current_temperature) can fail
                    # to resolve at all (renamed/suffixed entity, unavailable
                    # sensor, no device-paired sensor). Silently skipping here
                    # would drop that room's humidity from the scan entirely
                    # and could let the supply water run below its real dew
                    # point. Instead the zone contributes a non-real reading
                    # pinned to the system's blind floor, so it can still win
                    # worst-source selection but never forces the whole scan
                    # blind on its own. A present-but-implausible reading (a
                    # likely sensor fault, handled below) stays dropped.
                    readings.append(self.blind_zone_reading(zone_id, humidity_entity_id, now))
                continue

            reading = self._build_reading(zone_id, humidity_entity_id, temp_c, temp_source, now)
            if reading is not None:
                readings.append(reading)

        return readings

    def _scan_extra_sensors(self, now: datetime) -> list[SourceReading]:
        """Build readings for configured non-zone humidity/temperature pairs."""
        readings: list[SourceReading] = []
        for pair in self._extra_sensors:
            humidity_entity_id = pair.get("humidity")
            temperature_entity_id = pair.get("temperature")
            if not humidity_entity_id or not temperature_entity_id:
                continue

            temp_c = self._read_numeric_state(temperature_entity_id)
            if temp_c is None or not self._temp_plausible(temp_c):
                self._warn_once(
                    f"extra_temp:{temperature_entity_id}",
                    "Water temp control: temperature %s is missing or implausible (%s) — dropping source %s",
                    temperature_entity_id,
                    temp_c,
                    humidity_entity_id,
                )
                continue

            reading = self._build_reading(
                f"extra:{humidity_entity_id}",
                humidity_entity_id,
                temp_c,
                TEMP_SOURCE_ENTITY,
                now,
            )
            if reading is not None:
                readings.append(reading)

        return readings

    def _zone_humidity_paused(self, zone_data: dict[str, Any]) -> bool:
        """Return True when the zone's HumidityDetector is PAUSED/STABILIZING.

        Read from the climate entity's ``status`` attribute rather than the
        detector object so the scanner stays a pure ``hass.states`` consumer.
        """
        climate_entity_id = zone_data.get("climate_entity_id")
        if not climate_entity_id:
            return False
        state = self._hass.states.get(climate_entity_id)
        if state is None:
            return False
        status = state.attributes.get("status") or {}
        return any(override.get("type") == "humidity" for override in status.get("overrides", []) or [])

    # ── temperature pairing ──────────────────────────────────────────────────

    def _resolve_zone_temperature(self, zone_id: str, humidity_entity_id: str) -> tuple[float | None, str, bool]:
        """Resolve a co-located temperature for a zone humidity sensor.

        Order: (1) a temperature entity on the same device as the humidity
        sensor, (2) the zone climate entity's ``current_temperature``.  Pairing
        RH with a differently-placed temperature can eat the entire dew point
        margin, so the device match is strongly preferred.

        Returns:
            ``(temp_c, temp_source, unresolvable)``.  ``unresolvable`` is True
            only when no temperature reading could be obtained at all (entity
            missing / unavailable / non-numeric — see review finding #8) —
            as opposed to a present-but-implausible reading, which is a
            likely sensor fault and is dropped rather than treated as blind.
        """
        paired_entity_id = self._find_paired_temp_entity(humidity_entity_id)
        if paired_entity_id is not None:
            device_temp_c = self._read_numeric_state(paired_entity_id)
            if device_temp_c is not None and self._temp_plausible(device_temp_c):
                return device_temp_c, TEMP_SOURCE_DEVICE, False

        zone_temp_c = self._coordinator.get_zone_current_temp(zone_id)
        if zone_temp_c is not None and self._temp_plausible(zone_temp_c):
            if zone_id not in self._temp_source_logged:
                self._temp_source_logged.add(zone_id)
                _LOGGER.info(
                    "Water temp control: zone %s pairs humidity %s with the zone's "
                    "current_temperature (no temperature entity on the same device)",
                    zone_id,
                    humidity_entity_id,
                )
            return zone_temp_c, TEMP_SOURCE_CLIMATE, False

        if zone_temp_c is None:
            self._warn_once(
                f"zone_temp:{zone_id}",
                "Water temp control: no temperature available for zone %s — treating it as "
                "a blind source instead of dropping it",
                zone_id,
            )
            return None, TEMP_SOURCE_CLIMATE, True

        self._warn_once(
            f"zone_temp_implausible:{zone_id}",
            "Water temp control: zone %s temperature %.1f is outside the plausible band — dropping it",
            zone_id,
            zone_temp_c,
        )
        return None, TEMP_SOURCE_CLIMATE, False

    def _find_paired_temp_entity(self, humidity_entity_id: str) -> str | None:
        """Return a temperature sensor on the same device, if the registry knows one."""
        if er is None:
            return None
        try:
            registry = er.async_get(self._hass)
            entry = registry.async_get(humidity_entity_id)
            if entry is None or entry.device_id is None:
                return None
            for sibling in er.async_entries_for_device(registry, entry.device_id):
                if sibling.entity_id == humidity_entity_id or sibling.domain != "sensor":
                    continue
                device_class = sibling.device_class or sibling.original_device_class
                if device_class == "temperature":
                    return sibling.entity_id
        except (AttributeError, KeyError, TypeError):
            # HA boundary: registry shape varies across versions and is mocked in tests.
            return None
        return None

    # ── reading construction ─────────────────────────────────────────────────

    def _build_reading(
        self,
        key: str,
        humidity_entity_id: str,
        temp_c: float,
        temp_source: str,
        now: datetime,
    ) -> SourceReading | None:
        """Resolve RH for one source and compute its dew point."""
        rh_pct, real = self._resolve_humidity(key, humidity_entity_id, now)
        try:
            dew_point_c = dew_point(temp_c, rh_pct)
        except ValueError:
            self._warn_once(
                f"dewpoint:{key}",
                "Water temp control: cannot compute dew point for %s (temp=%.1f, rh=%.1f)",
                key,
                temp_c,
                rh_pct,
            )
            return None

        return SourceReading(
            key=key,
            rh_pct=rh_pct,
            temp_c=temp_c,
            dew_point_c=dew_point_c,
            real=real,
            temp_source=temp_source,
        )

    def blind_zone_reading(self, zone_id: str, humidity_entity_id: str, now: datetime) -> SourceReading:
        """Build a conservative stand-in reading for a COOL zone with no usable temperature.

        Public (review finding #11): reused by
        :mod:`.water_temp_blind_zones` for registered zones whose HVAC mode
        can't be resolved at all, not just an internal scanner detail.

        Review finding #8: dropping such a zone entirely would exclude its
        humidity signal from the scan.  Instead it contributes a dew point that
        pulls the effective target up to exactly the system's blind floor
        (:data:`WATER_TEMP_BLIND_MIN_SUPPLY`) — conservative because it can
        still win worst-source selection, but (being non-real) never by itself
        forces the whole scan blind when another zone has a genuine reading.

        The stand-in is ``floor - dew_point_margin``, not the floor itself:
        every consumer adds ``dew_point_margin`` to whatever dew point the scan
        reports, and :data:`WATER_TEMP_BLIND_MIN_SUPPLY` is already a *supply
        water* bound rather than a room air measurement.  Pinning the raw floor
        here fed it through that same ``+ margin`` step and landed the target a
        full margin above the floor, so a zone with no usable temperature
        demanded warmer water than a system with no dew point information at
        all (which returns the bare floor).  Less information must not change
        the answer in either direction.
        """
        rh_pct = self._resolve_humidity(zone_id, humidity_entity_id, now)[0]
        stand_in_c = WATER_TEMP_BLIND_MIN_SUPPLY - self._dew_point_margin
        return SourceReading(
            key=zone_id,
            rh_pct=rh_pct,
            temp_c=stand_in_c,
            dew_point_c=stand_in_c,
            real=False,
            temp_source=TEMP_SOURCE_CLIMATE,
        )

    def _resolve_humidity(self, key: str, humidity_entity_id: str, now: datetime) -> tuple[float, bool]:
        """Return the effective RH for a source and whether it is a real reading."""
        state = self._hass.states.get(humidity_entity_id)
        if state is None:
            return self._degraded_humidity(key), False

        if self._is_stale(state, now):
            self._warn_once(
                f"stale:{key}",
                "Water temp control: humidity %s is stale — using max(last EMA, fallback)",
                humidity_entity_id,
            )
            return self._degraded_humidity(key), False

        raw = self._to_float(state.state)
        if raw is None or not (WATER_TEMP_RH_MIN <= raw <= WATER_TEMP_RH_MAX):
            self._warn_once(
                f"implausible:{key}",
                "Water temp control: humidity %s reads %s (outside %.0f-%.0f%%) — using fallback %.0f%%",
                humidity_entity_id,
                state.state,
                WATER_TEMP_RH_MIN,
                WATER_TEMP_RH_MAX,
                self._fallback_humidity,
            )
            return self._degraded_humidity(key), False

        return self._update_ema(key, raw, now), True

    def _degraded_humidity(self, key: str) -> float:
        """RH to use when a source has no usable reading.

        ``max(last_ema, fallback)`` so a known-humid zone is not optimistically
        forgotten when its sensor goes quiet.
        """
        last_ema = self._ema.get(key)
        if last_ema is None:
            return self._fallback_humidity
        return max(last_ema, self._fallback_humidity)

    def _update_ema(self, key: str, raw_rh: float, now: datetime) -> float:
        """Advance the per-source RH EMA and return the smoothed value."""
        previous = self._ema.get(key)
        last_updated = self._ema_updated.get(key)
        if previous is None or last_updated is None:
            self._ema[key] = raw_rh
            self._ema_updated[key] = now
            return raw_rh

        dt_minutes = max(0.0, (now - last_updated).total_seconds() / 60.0)
        alpha = 1.0 - math.exp(-dt_minutes / self._ema_window_minutes) if self._ema_window_minutes > 0 else 1.0
        smoothed = previous + alpha * (raw_rh - previous)
        self._ema[key] = smoothed
        self._ema_updated[key] = now
        return smoothed

    # ── small helpers ────────────────────────────────────────────────────────

    def _is_stale(self, state: Any, now: datetime) -> bool:
        """Return True when the state's last_updated is older than the threshold."""
        last_updated = getattr(state, "last_updated", None)
        if last_updated is None:
            return False
        try:
            age_minutes = (now - last_updated).total_seconds() / 60.0
        except TypeError:
            return False
        return age_minutes > self._stale_after_minutes

    def _read_numeric_state(self, entity_id: str) -> float | None:
        """Read an entity's state as a float, or None."""
        state = self._hass.states.get(entity_id)
        if state is None:
            return None
        return self._to_float(state.state)

    @staticmethod
    def _to_float(value: Any) -> float | None:
        """Coerce a state value to float, or None."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _temp_plausible(temp_c: float) -> bool:
        """Return True when an air temperature is inside the plausible band."""
        return WATER_TEMP_AIR_TEMP_MIN <= temp_c <= WATER_TEMP_AIR_TEMP_MAX

    def _warn_once(self, key: str, message: str, *args: Any) -> None:
        """Emit a WARNING at most once per WATER_TEMP_WARN_INTERVAL_SECONDS per key."""
        from homeassistant.util import dt as dt_util

        now = dt_util.utcnow()
        last = self._last_warned.get(key)
        if last is not None and (now - last).total_seconds() < WATER_TEMP_WARN_INTERVAL_SECONDS:
            return
        self._last_warned[key] = now
        _LOGGER.warning(message, *args)
