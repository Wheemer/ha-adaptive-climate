"""Water temperature control: dew-point cooling, heating target, startup ramps.

Owns the effective supply-water temperature for each HVAC mode and pushes it to
external ``number`` / ``input_number`` entities consumed by the heat pump or
mixing valve.  Named ``*Controller`` (matching ``heater_controller.py``) because
it actuates external hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import math
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_WATER_TEMP_COOLING,
    CONF_WATER_TEMP_DEW_POINT_MARGIN,
    CONF_WATER_TEMP_EXTRA_SENSORS,
    CONF_WATER_TEMP_FALLBACK_HUMIDITY,
    CONF_WATER_TEMP_HEATING,
    CONF_WATER_TEMP_IDLE_DAYS,
    CONF_WATER_TEMP_MIN_SUPPLY_TEMP,
    CONF_WATER_TEMP_MIN_WRITE_INTERVAL,
    CONF_WATER_TEMP_CONDENSATION_SENSOR,
    CONF_WATER_TEMP_RAMP_RATE,
    CONF_WATER_TEMP_RAMP_START,
    CONF_WATER_TEMP_TARGET,
    CONF_WATER_TEMP_TARGET_ENTITY,
    DEFAULT_WATER_TEMP_COOLING_RAMP_RATE,
    DEFAULT_WATER_TEMP_COOLING_RAMP_START,
    DEFAULT_WATER_TEMP_DEW_POINT_MARGIN,
    DEFAULT_WATER_TEMP_FALLBACK_HUMIDITY,
    DEFAULT_WATER_TEMP_HEATING_RAMP_RATE,
    DEFAULT_WATER_TEMP_HEATING_RAMP_START,
    DEFAULT_WATER_TEMP_IDLE_DAYS,
    DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP,
    DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL,
    DEFAULT_WATER_TEMP_STEP,
    SUPPLY_TEMP_MAX,
    SUPPLY_TEMP_MIN,
    WATER_TEMP_BINDING_BLIND,
    WATER_TEMP_BINDING_DEW_POINT,
    WATER_TEMP_BINDING_MIN_SUPPLY,
    WATER_TEMP_BINDING_RAMP,
    WATER_TEMP_BINDING_TARGET,
    WATER_TEMP_BLIND_MIN_SUPPLY,
    WATER_TEMP_GATE_WRITE_DELTA,
    WATER_TEMP_MODE_COOLING,
    WATER_TEMP_MODE_HEATING,
    WATER_TEMP_SETTLING_MINUTES,
    WATER_TEMP_WARN_INTERVAL_SECONDS,
)
from .heater_service_caller import HeaterServiceCaller
from .water_temp_sources import DewPointScan, DewPointScanner

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..coordinator import AdaptiveThermostatCoordinator

_LOGGER = logging.getLogger(__name__)

_SECONDS_PER_DAY = 86400.0

MODE_HVAC_STATE = {
    WATER_TEMP_MODE_COOLING: "cool",
    WATER_TEMP_MODE_HEATING: "heat",
}


@dataclass
class ModeRampState:
    """Idle / ramp bookkeeping for one mode.

    All timestamps are wall-clock ``dt_util.utcnow()`` values persisted as ISO
    strings — never ``time.monotonic()``, which resets on restart.
    """

    last_active: datetime | None = None
    ramp_started: datetime | None = None
    ramp_start_value: float | None = None


class WaterTempController:
    """Compute and write supply water temperature setpoints."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: AdaptiveThermostatCoordinator,
        config: dict[str, Any],
        supply_temperature: float | None = None,
    ) -> None:
        """Initialize the controller.

        Args:
            hass: Home Assistant instance.
            coordinator: Zone registry, used for per-mode zone lookups.
            config: The validated ``water_temp_control`` sub-dict.
            supply_temperature: Domain-level ``supply_temperature``, the fallback
                for ``heating.target``.  Passed in rather than read from
                ``hass.data`` because the coordinator is constructed before
                ``hass.data[DOMAIN]["supply_temperature"]`` is written.
        """
        self.hass = hass
        self._coordinator = coordinator

        self._idle_days = float(config.get(CONF_WATER_TEMP_IDLE_DAYS, DEFAULT_WATER_TEMP_IDLE_DAYS))
        self._min_write_interval = float(
            config.get(CONF_WATER_TEMP_MIN_WRITE_INTERVAL, DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL)
        )
        self._condensation_sensor: str | None = config.get(CONF_WATER_TEMP_CONDENSATION_SENSOR)

        self._cooling: dict[str, Any] | None = config.get(CONF_WATER_TEMP_COOLING)
        self._heating: dict[str, Any] | None = config.get(CONF_WATER_TEMP_HEATING)

        self._heating_target: float | None = None
        if self._heating is not None:
            configured = self._heating.get(CONF_WATER_TEMP_TARGET)
            self._heating_target = (
                float(configured)
                if configured is not None
                else (float(supply_temperature) if supply_temperature is not None else None)
            )

        self._scanner: DewPointScanner | None = None
        if self._cooling is not None:
            self._scanner = DewPointScanner(
                hass,
                coordinator,
                extra_sensors=self._cooling.get(CONF_WATER_TEMP_EXTRA_SENSORS, []) or [],
                fallback_humidity=float(
                    self._cooling.get(CONF_WATER_TEMP_FALLBACK_HUMIDITY, DEFAULT_WATER_TEMP_FALLBACK_HUMIDITY)
                ),
            )

        self._ramp: dict[str, ModeRampState] = {
            WATER_TEMP_MODE_COOLING: ModeRampState(),
            WATER_TEMP_MODE_HEATING: ModeRampState(),
        }
        self._binding: dict[str, str] = {}
        self._effective: dict[str, float] = {}
        self._last_scan: DewPointScan | None = None
        self._restored = False

        self._last_written: dict[str, float] = {}
        self._pending: dict[str, tuple[float, datetime]] = {}
        self._gate_until: dict[str, datetime] = {}
        self._was_active: dict[str, bool] = {
            WATER_TEMP_MODE_COOLING: False,
            WATER_TEMP_MODE_HEATING: False,
        }
        self._last_write_error: dict[str, datetime] = {}

    # ── introspection ────────────────────────────────────────────────────────

    @property
    def enabled_modes(self) -> tuple[str, ...]:
        """Return the configured mode keys."""
        modes = []
        if self._cooling is not None:
            modes.append(WATER_TEMP_MODE_COOLING)
        if self._heating is not None:
            modes.append(WATER_TEMP_MODE_HEATING)
        return tuple(modes)

    @property
    def ramp_state(self) -> dict[str, ModeRampState]:
        """Return the per-mode ramp state (read-only use)."""
        return self._ramp

    @property
    def binding(self) -> dict[str, str]:
        """Return the per-mode binding constraint from the last computation."""
        return self._binding

    @property
    def restored(self) -> bool:
        """Return True once persisted state has been applied (or found absent)."""
        return self._restored

    @property
    def effective_cooling_supply_temp(self) -> float | None:
        """Return the current effective cooling supply temp, or None."""
        return self._effective.get(WATER_TEMP_MODE_COOLING)

    @staticmethod
    def _utcnow() -> datetime:
        """Return current wall-clock UTC (indirection keeps tests deterministic)."""
        return dt_util.utcnow()

    # ── persistence ──────────────────────────────────────────────────────────

    def get_state_for_persistence(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of ramp and write state."""
        state: dict[str, Any] = {}
        for mode, ramp in self._ramp.items():
            state[mode] = {
                "last_active": ramp.last_active.isoformat() if ramp.last_active else None,
                "ramp_started": ramp.ramp_started.isoformat() if ramp.ramp_started else None,
                "ramp_start_value": ramp.ramp_start_value,
            }
        state["last_written"] = dict(getattr(self, "_last_written", {}))
        return state

    def restore_state(self, state: dict[str, Any] | None) -> None:
        """Restore ramp and write state from persistence.

        Guards against clock corrections by clamping any future timestamp to
        "now" — a persisted ``ramp_started`` in the future would otherwise
        produce a negative elapsed time.

        Args:
            state: Previously persisted dict, or None on first run.
        """
        if state:
            now = self._utcnow()
            for mode in (WATER_TEMP_MODE_COOLING, WATER_TEMP_MODE_HEATING):
                mode_state = state.get(mode) or {}
                ramp = self._ramp[mode]
                ramp.last_active = self._parse_timestamp(mode_state.get("last_active"), now)
                ramp.ramp_started = self._parse_timestamp(mode_state.get("ramp_started"), now)
                value = mode_state.get("ramp_start_value")
                ramp.ramp_start_value = float(value) if isinstance(value, (int, float)) else None

            last_written = state.get("last_written")
            if isinstance(last_written, dict):
                self._last_written = {
                    entity_id: float(value)
                    for entity_id, value in last_written.items()
                    if isinstance(value, (int, float))
                }

        self.mark_restored()

    def mark_restored(self) -> None:
        """Mark state as restored so computation may begin."""
        self._restored = True

    @staticmethod
    def _parse_timestamp(value: Any, now: datetime) -> datetime | None:
        """Parse an ISO timestamp, clamping future values to ``now``."""
        if not isinstance(value, str):
            return None
        parsed = dt_util.parse_datetime(value)
        if parsed is None:
            return None
        return min(parsed, now)

    # ── computation ──────────────────────────────────────────────────────────

    def compute_targets(self, now: datetime) -> dict[str, float]:
        """Compute the effective supply temperature for every active mode.

        Args:
            now: Current wall-clock time.

        Returns:
            Mapping of mode key -> effective supply temperature in °C.  Modes
            that are not configured or have no zones in that mode are absent.
        """
        if not self._restored:
            _LOGGER.debug("Water temp control: state not restored yet, skipping computation")
            return {}

        targets: dict[str, float] = {}
        self._last_scan = None

        if self._cooling is not None:
            value = self._compute_cooling(now)
            if value is not None:
                targets[WATER_TEMP_MODE_COOLING] = value

        if self._heating is not None:
            value = self._compute_heating(now)
            if value is not None:
                targets[WATER_TEMP_MODE_HEATING] = value

        self._effective = dict(targets)
        return targets

    def _compute_cooling(self, now: datetime) -> float | None:
        """Compute the effective cooling supply temperature, or None if inactive."""
        if not self._mode_is_active(WATER_TEMP_MODE_COOLING):
            return None

        cooling = self._cooling or {}
        min_supply = float(cooling.get(CONF_WATER_TEMP_MIN_SUPPLY_TEMP, DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP))
        margin = float(cooling.get(CONF_WATER_TEMP_DEW_POINT_MARGIN, DEFAULT_WATER_TEMP_DEW_POINT_MARGIN))

        scan = self._scanner.scan(now) if self._scanner is not None else None
        self._last_scan = scan

        if scan is None or scan.blind or scan.dew_point is None:
            dew_target = max(min_supply, WATER_TEMP_BLIND_MIN_SUPPLY)
            binding = WATER_TEMP_BINDING_BLIND
        else:
            with_margin = scan.dew_point + margin
            if with_margin >= min_supply:
                dew_target, binding = with_margin, WATER_TEMP_BINDING_DEW_POINT
            else:
                dew_target, binding = min_supply, WATER_TEMP_BINDING_MIN_SUPPLY

        self._update_ramp(WATER_TEMP_MODE_COOLING, now, seed_from_entity=False)
        ramp = self._ramp[WATER_TEMP_MODE_COOLING]

        if ramp.ramp_started is not None and ramp.ramp_start_value is not None:
            rate = float(cooling.get(CONF_WATER_TEMP_RAMP_RATE, DEFAULT_WATER_TEMP_COOLING_RAMP_RATE))
            ramp_value = ramp.ramp_start_value - rate * self._days_since(ramp.ramp_started, now)
            if ramp_value > dew_target:
                self._binding[WATER_TEMP_MODE_COOLING] = WATER_TEMP_BINDING_RAMP
                return ramp_value
            self._end_ramp(WATER_TEMP_MODE_COOLING)

        self._binding[WATER_TEMP_MODE_COOLING] = binding
        return dew_target

    def _compute_heating(self, now: datetime) -> float | None:
        """Compute the effective heating supply temperature, or None if inactive."""
        if not self._mode_is_active(WATER_TEMP_MODE_HEATING):
            return None
        if self._heating_target is None:
            _LOGGER.warning("Water temp control: heating configured without a resolvable target")
            return None

        self._update_ramp(WATER_TEMP_MODE_HEATING, now, seed_from_entity=True)
        ramp = self._ramp[WATER_TEMP_MODE_HEATING]
        heating = self._heating or {}

        if ramp.ramp_started is not None and ramp.ramp_start_value is not None:
            rate = float(heating.get(CONF_WATER_TEMP_RAMP_RATE, DEFAULT_WATER_TEMP_HEATING_RAMP_RATE))
            ramp_value = ramp.ramp_start_value + rate * self._days_since(ramp.ramp_started, now)
            if ramp_value < self._heating_target:
                self._binding[WATER_TEMP_MODE_HEATING] = WATER_TEMP_BINDING_RAMP
                return ramp_value
            self._end_ramp(WATER_TEMP_MODE_HEATING)

        self._binding[WATER_TEMP_MODE_HEATING] = WATER_TEMP_BINDING_TARGET
        return self._heating_target

    # ── ramp lifecycle ───────────────────────────────────────────────────────

    def _update_ramp(self, mode: str, now: datetime, seed_from_entity: bool) -> None:
        """Start a ramp when the mode resumes after >= idle_days inactive."""
        ramp = self._ramp[mode]

        if ramp.last_active is None:
            idle_days = float("inf")  # first run: treat as long-idle, ramp conservatively
        else:
            idle_days = max(0.0, self._days_since(ramp.last_active, now))

        if ramp.ramp_started is None and idle_days >= self._idle_days:
            ramp.ramp_started = now
            ramp.ramp_start_value = self._seed_ramp_start(mode, seed_from_entity)
            _LOGGER.info(
                "Water temp control: starting %s ramp from %.1f°C (idle for %.1f days)",
                mode,
                ramp.ramp_start_value,
                idle_days if idle_days != float("inf") else -1.0,
            )

        ramp.last_active = now

    def _seed_ramp_start(self, mode: str, seed_from_entity: bool) -> float:
        """Return the value a new ramp starts from.

        Heating seeds from ``max(configured ramp_start, current entity value)``
        so a system already running hot is never yanked down (backup-heater
        trap).  Cooling always uses the configured ``ramp_start`` — seeding from
        the entity would start too cold on a warm slab.
        """
        config = self._heating if mode == WATER_TEMP_MODE_HEATING else self._cooling
        default = (
            DEFAULT_WATER_TEMP_HEATING_RAMP_START
            if mode == WATER_TEMP_MODE_HEATING
            else DEFAULT_WATER_TEMP_COOLING_RAMP_START
        )
        configured = float((config or {}).get(CONF_WATER_TEMP_RAMP_START, default))

        if not seed_from_entity:
            return configured

        current = self._read_entity_value(self._target_entity(mode))
        if current is None:
            return configured
        return max(configured, current)

    def _end_ramp(self, mode: str) -> None:
        """Clear ramp state once the ramp bound stops binding."""
        ramp = self._ramp[mode]
        if ramp.ramp_started is not None:
            _LOGGER.info("Water temp control: %s ramp complete", mode)
        ramp.ramp_started = None
        ramp.ramp_start_value = None

    @staticmethod
    def _days_since(start: datetime, now: datetime) -> float:
        """Return elapsed days, clamped at >= 0 to survive clock corrections."""
        return max(0.0, (now - start).total_seconds() / _SECONDS_PER_DAY)

    # ── entity helpers ───────────────────────────────────────────────────────

    def _mode_is_active(self, mode: str) -> bool:
        """Return True when at least one zone's climate entity is in this mode."""
        return bool(self._coordinator.get_zones_in_mode(MODE_HVAC_STATE[mode]))

    def _target_entity(self, mode: str) -> str:
        """Return the configured target entity id for a mode."""
        config = self._heating if mode == WATER_TEMP_MODE_HEATING else self._cooling
        return str((config or {}).get(CONF_WATER_TEMP_TARGET_ENTITY, ""))

    def _read_entity_value(self, entity_id: str) -> float | None:
        """Read a number entity's current value as a float, or None."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None:
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    # ── apply cycle ──────────────────────────────────────────────────────────

    async def async_apply(self, now: datetime) -> None:
        """Compute targets and push them to the configured entities.

        Args:
            now: Current wall-clock time.
        """
        targets = self.compute_targets(now)

        for mode in self.enabled_modes:
            entity_id = self._target_entity(mode)
            if not entity_id:
                continue

            value = targets.get(mode)
            if value is not None:
                self._was_active[mode] = True
                await self._async_write(mode, entity_id, value, now=now)
                continue

            if self._was_active[mode]:
                # Mode just deactivated: park at ramp_start rather than leaving
                # the most aggressive value latched for the next season.
                self._was_active[mode] = False
                park_value = self._park_value(mode)
                _LOGGER.info("Water temp control: %s deactivated, parking at %.1f°C", mode, park_value)
                await self._async_write(mode, entity_id, park_value, now=now, force=True)

    def _park_value(self, mode: str) -> float:
        """Return the configured ramp_start used as this mode's park value."""
        config = self._heating if mode == WATER_TEMP_MODE_HEATING else self._cooling
        default = (
            DEFAULT_WATER_TEMP_HEATING_RAMP_START
            if mode == WATER_TEMP_MODE_HEATING
            else DEFAULT_WATER_TEMP_COOLING_RAMP_START
        )
        return float((config or {}).get(CONF_WATER_TEMP_RAMP_START, default))

    # ── write policy ─────────────────────────────────────────────────────────

    async def _async_write(
        self,
        mode: str,
        entity_id: str,
        value: float,
        *,
        now: datetime,
        force: bool = False,
    ) -> bool:
        """Round, clamp and conditionally write a supply temperature.

        Args:
            mode: Mode key the value belongs to.
            entity_id: Target ``number`` / ``input_number`` entity.
            value: Unrounded, unclamped desired value in °C.
            now: Current wall-clock time.
            force: Bypass the unsafe-direction dwell (parks and interlocks).

        Returns:
            True when a service call was issued and accepted.
        """
        minimum, maximum, step = self._entity_limits(entity_id)
        final = min(max(self._round_safe(value, mode, step), minimum), maximum)

        last = self._last_written.get(entity_id)
        # Compare the post-clamp, post-round value: comparing the raw value
        # would re-issue identical calls forever when the target is out of range.
        if last is not None and abs(final - last) < 1e-6:
            self._pending.pop(entity_id, None)
            return False

        if not force and last is not None and not self._is_safe_direction(mode, final, last):
            pending = self._pending.get(entity_id)
            if pending is None or abs(pending[0] - final) > 1e-6:
                self._pending[entity_id] = (final, now)
                return False
            if (now - pending[1]).total_seconds() < self._min_write_interval:
                return False

        if not await self._async_call_set_value(entity_id, final, now):
            return False

        self._pending.pop(entity_id, None)
        if last is not None and abs(final - last) >= WATER_TEMP_GATE_WRITE_DELTA:
            self._gate_until[mode] = now + timedelta(minutes=WATER_TEMP_SETTLING_MINUTES)
        self._last_written[entity_id] = final
        return True

    @staticmethod
    def _is_safe_direction(mode: str, new_value: float, last_value: float) -> bool:
        """Return True when the change moves in the condensation-safe direction.

        Cooling: warmer water is safer (up).  Heating: cooler water is safer (down).
        """
        if mode == WATER_TEMP_MODE_COOLING:
            return new_value > last_value
        return new_value < last_value

    @staticmethod
    def _round_safe(value: float, mode: str, step: float) -> float:
        """Round to the entity step, always toward the safe side."""
        if step <= 0:
            return round(value, 3)
        if mode == WATER_TEMP_MODE_COOLING:
            return round(math.ceil(value / step - 1e-9) * step, 3)
        return round(math.floor(value / step + 1e-9) * step, 3)

    def _entity_limits(self, entity_id: str) -> tuple[float, float, float]:
        """Return the target entity's (min, max, step), with safe fallbacks."""
        state = self.hass.states.get(entity_id)
        if state is None:
            return SUPPLY_TEMP_MIN, SUPPLY_TEMP_MAX, DEFAULT_WATER_TEMP_STEP

        attributes = state.attributes or {}
        step = self._coerce(attributes.get("step"), DEFAULT_WATER_TEMP_STEP)
        if step <= 0:
            step = DEFAULT_WATER_TEMP_STEP
        minimum = self._coerce(attributes.get("min"), SUPPLY_TEMP_MIN)
        maximum = self._coerce(attributes.get("max"), SUPPLY_TEMP_MAX)
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        return minimum, maximum, step

    @staticmethod
    def _coerce(value: Any, default: float) -> float:
        """Coerce an attribute to float, falling back to a default."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    async def _async_call_set_value(self, entity_id: str, value: float, now: datetime) -> bool:
        """Call ``set_value`` on the target entity, handling all error types.

        Mirrors :class:`HeaterServiceCaller` error handling; failures are logged
        (rate-limited) and simply retried on the next cycle.
        """
        domain = HeaterServiceCaller.get_number_entity_domain(entity_id)
        try:
            await self.hass.services.async_call(
                domain,
                "set_value",
                {"entity_id": entity_id, "value": value},
                blocking=False,
            )
            self._last_write_error.pop(entity_id, None)
            _LOGGER.debug("Water temp control: wrote %.1f°C to %s", value, entity_id)
            return True
        except ServiceNotFound as err:
            self._log_write_error(entity_id, now, "service '%s.set_value' not found: %s", domain, err)
            return False
        except HomeAssistantError as err:
            self._log_write_error(entity_id, now, "Home Assistant error: %s", err)
            return False
        except Exception as err:  # broad: one bad entity must not kill the cycle
            self._log_write_error(entity_id, now, "unexpected error: %s", err)
            return False

    def _log_write_error(self, entity_id: str, now: datetime, message: str, *args: Any) -> None:
        """Log a write failure at most once per hour per entity."""
        last = self._last_write_error.get(entity_id)
        if last is not None and (now - last).total_seconds() < WATER_TEMP_WARN_INTERVAL_SECONDS:
            return
        self._last_write_error[entity_id] = now
        _LOGGER.error("Water temp control: failed to write %s — " + message, entity_id, *args)
