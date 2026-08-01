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
from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CALLBACK_TYPE
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.helpers.event import async_call_later, async_track_time_interval
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
    CONF_WATER_TEMP_TARGET,
    CONF_WATER_TEMP_TARGET_ENTITY,
    DEFAULT_WATER_TEMP_DEW_POINT_MARGIN,
    DEFAULT_WATER_TEMP_FALLBACK_HUMIDITY,
    DEFAULT_WATER_TEMP_IDLE_DAYS,
    DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP,
    DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL,
    WATER_TEMP_BINDING_BLIND,
    WATER_TEMP_BINDING_DEW_POINT,
    WATER_TEMP_BINDING_ENTITY_LIMIT,
    WATER_TEMP_BINDING_INTERLOCK,
    WATER_TEMP_BINDING_MIN_SUPPLY,
    WATER_TEMP_BINDING_RAMP,
    WATER_TEMP_BINDING_TARGET,
    WATER_TEMP_BLIND_MIN_SUPPLY,
    WATER_TEMP_GATE_WRITE_DELTA,
    WATER_TEMP_MODE_COOLING,
    WATER_TEMP_MODE_HEATING,
    WATER_TEMP_SETTLING_MINUTES,
    WATER_TEMP_STARTUP_DELAY_SECONDS,
    WATER_TEMP_UPDATE_INTERVAL_SECONDS,
    WATER_TEMP_WARN_INTERVAL_SECONDS,
)
from .heater_service_caller import HeaterServiceCaller
from .water_temp_blind_zones import merge_unresolvable_zone_readings
from .water_temp_interlocks import CoolingInterlockManager
from .water_temp_sources import DewPointScan, DewPointScanner
from .water_temp_writer import (
    configured_ramp_rate,
    configured_ramp_start,
    elapsed_days,
    entity_limit_binds,
    entity_limits,
    is_safe_direction,
    ramp_origin,
    round_safe,
    warn_entity_limited,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..coordinator import AdaptiveThermostatCoordinator

_LOGGER = logging.getLogger(__name__)

MODE_HVAC_STATE = {
    WATER_TEMP_MODE_COOLING: "cool",
    WATER_TEMP_MODE_HEATING: "heat",
}


@dataclass
class ModeRampState:
    """Idle / ramp bookkeeping for one mode.

    All timestamps are wall-clock ``dt_util.utcnow()`` values persisted as ISO
    strings — never ``time.monotonic()``, which resets on restart.

    ``ramp_start_value`` is the value a ramp started from. Cooling ignores
    it in the ramp math (``ramp_start`` is read live from config each
    compute) and keeps it only for logging. Heating persists it as a seed
    floor under the live configured ``ramp_start`` (backup-heater trap).
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
            supply_temperature: Domain-level ``supply_temperature``, the
                ``heating.target`` fallback. Passed in (not read from
                ``hass.data``) since the coordinator predates that key.
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
        self._last_entity_limit_warned: dict[str, datetime] = {}

        self._interlock = CoolingInterlockManager(
            hass, coordinator, self._condensation_sensor, MODE_HVAC_STATE[WATER_TEMP_MODE_COOLING]
        )
        self._started_unsub: CALLBACK_TYPE | None = None
        self._startup_unsub: CALLBACK_TYPE | None = None
        self._interval_unsub: CALLBACK_TYPE | None = None

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
        """Return a JSON-serializable snapshot of ramp and write state.

        Only the heating seed is persisted under ``ramp_start_value``:
        cooling's ramp origin is read live from config each compute, so
        there is nothing worth persisting for it (R13).
        """
        state: dict[str, Any] = {}
        for mode, ramp in self._ramp.items():
            state[mode] = {
                "last_active": ramp.last_active.isoformat() if ramp.last_active else None,
                "ramp_started": ramp.ramp_started.isoformat() if ramp.ramp_started else None,
                "ramp_start_value": ramp.ramp_start_value if mode == WATER_TEMP_MODE_HEATING else None,
            }
        state["last_written"] = dict(getattr(self, "_last_written", {}))
        return state

    def restore_state(self, state: dict[str, Any] | None) -> None:
        """Restore ramp and write state from persistence.

        Clamps any future timestamp to "now" to guard against clock
        corrections — a persisted ``ramp_started`` in the future would
        otherwise produce a negative elapsed time.

        Transparently migrates old-format stores that persisted
        ``ramp_start_value`` for both modes (R13): cooling's stored value is
        ignored (live config is authoritative), heating's is restored as
        the seed. No storage version bump needed since the key is unchanged.

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
                if mode == WATER_TEMP_MODE_HEATING:
                    value = mode_state.get("ramp_start_value")
                    ramp.ramp_start_value = float(value) if isinstance(value, (int, float)) else None
                else:
                    ramp.ramp_start_value = None

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
        # #10: reset here too (not just inside evaluate()) so a stale True
        # can't leak into a cycle where cooling goes inactive before the
        # interlock is ever reached.
        self._interlock.just_cleared = False

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
            # N1 (BLOCKER): an interlock means nothing when no zone cools --
            # reset it so a season-end interlock can't freeze its "engaged
            # at" timestamp across the off-season.
            self._interlock.reset()
            return None

        cooling = self._cooling or {}
        min_supply = float(cooling.get(CONF_WATER_TEMP_MIN_SUPPLY_TEMP, DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP))
        margin = float(cooling.get(CONF_WATER_TEMP_DEW_POINT_MARGIN, DEFAULT_WATER_TEMP_DEW_POINT_MARGIN))

        # Scanned before the interlock check: the park value needs "current
        # dew target" even when about to park instead of returning it.
        dew_target, binding, scan = self._resolve_cooling_dew_target(now, min_supply, margin)
        self._last_scan = scan

        if self._interlock.evaluate(now, self._ramp[WATER_TEMP_MODE_COOLING]):
            self._binding[WATER_TEMP_MODE_COOLING] = WATER_TEMP_BINDING_INTERLOCK
            return self._interlock.park_value(self._park_value(WATER_TEMP_MODE_COOLING), dew_target)

        self._update_ramp(WATER_TEMP_MODE_COOLING, now, seed_from_entity=False)
        ramp = self._ramp[WATER_TEMP_MODE_COOLING]

        if ramp.ramp_started is not None:
            # R13: origin is read live from config every compute -- no
            # persisted value -- so a mid-ramp ramp_start edit applies on
            # the very next cycle instead of needing .storage surgery.
            rate = configured_ramp_rate(WATER_TEMP_MODE_COOLING, cooling)
            origin = configured_ramp_start(WATER_TEMP_MODE_COOLING, cooling)
            ramp_value = origin - rate * elapsed_days(ramp.ramp_started, now)
            if ramp_value > dew_target:
                self._binding[WATER_TEMP_MODE_COOLING] = WATER_TEMP_BINDING_RAMP
                return ramp_value
            self._end_ramp(WATER_TEMP_MODE_COOLING)

        self._binding[WATER_TEMP_MODE_COOLING] = binding
        return dew_target

    def _resolve_cooling_dew_target(
        self, now: datetime, min_supply: float, margin: float
    ) -> tuple[float, str, DewPointScan | None]:
        """Scan for the worst-case dew point and resolve the (unramped) target.

        Shared by the normal compute path and the interlock park value
        (``max(ramp_start, current dew target)``, so an interlock can never
        park below what condensation safety currently requires).

        The blind case is a FLOOR on top of whatever degraded dew point was
        actually computed (fallback humidity + a real temperature still
        produces a usable, if non-"real", ``scan.dew_point``) — not a flat
        replacement. Only a scan with no dew point at all falls back to the
        bare floor.
        """
        scan = self._scanner.scan(now) if self._scanner is not None else None
        scan = merge_unresolvable_zone_readings(
            scan,
            hass=self.hass,
            coordinator=self._coordinator,
            scanner=self._scanner,
            cool_hvac_state=MODE_HVAC_STATE[WATER_TEMP_MODE_COOLING],
            now=now,
        )

        if scan is None or scan.dew_point is None:
            return max(min_supply, WATER_TEMP_BLIND_MIN_SUPPLY), WATER_TEMP_BINDING_BLIND, scan

        if scan.blind:
            floored = max(scan.dew_point + margin, min_supply, WATER_TEMP_BLIND_MIN_SUPPLY)
            return floored, WATER_TEMP_BINDING_BLIND, scan

        with_margin = scan.dew_point + margin
        if with_margin >= min_supply:
            return with_margin, WATER_TEMP_BINDING_DEW_POINT, scan
        return min_supply, WATER_TEMP_BINDING_MIN_SUPPLY, scan

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

        if ramp.ramp_started is not None:
            # R13: origin = max(live config ramp_start, persisted entity
            # seed) -- config is read live so a raise applies mid-ramp, but
            # a higher seed (backup-heater trap) still wins.
            rate = configured_ramp_rate(WATER_TEMP_MODE_HEATING, heating)
            configured_start = configured_ramp_start(WATER_TEMP_MODE_HEATING, heating)
            origin = ramp_origin(configured_start, ramp.ramp_start_value)
            ramp_value = origin + rate * elapsed_days(ramp.ramp_started, now)
            if ramp_value < self._heating_target:
                self._binding[WATER_TEMP_MODE_HEATING] = WATER_TEMP_BINDING_RAMP
                return ramp_value
            self._end_ramp(WATER_TEMP_MODE_HEATING)

        self._binding[WATER_TEMP_MODE_HEATING] = WATER_TEMP_BINDING_TARGET
        return self._heating_target

    # ── ramp lifecycle ───────────────────────────────────────────────────────

    def _update_ramp(self, mode: str, now: datetime, seed_from_entity: bool) -> None:
        """Start (or restart) a ramp when the mode has been idle >= idle_days.

        Restarts even mid-ramp ("stale" case): a mode that goes inactive
        before the ramp completes leaves ``ramp_started`` frozen, since this
        method isn't called while inactive. Without restarting, reactivation
        computes an enormous elapsed time against that stale timestamp and
        the full step lands in one write instead of a fresh ramp. A gap
        shorter than ``idle_days`` preserves the in-progress ramp's own start.

        By design, ANY gap >= ``idle_days`` between two calls restarts the
        ramp — ``last_active`` only advances here, so the 5-minute production
        timer makes a spurious restart (vs. a genuine idle gap) unreachable
        in practice, and conservative either way.
        """
        ramp = self._ramp[mode]

        if ramp.last_active is None:
            idle_days = float("inf")  # first run: treat as long-idle, ramp conservatively
        else:
            idle_days = max(0.0, elapsed_days(ramp.last_active, now))

        if idle_days >= self._idle_days:
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
        configured = configured_ramp_start(mode, config)

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
                interlocked = mode == WATER_TEMP_MODE_COOLING and (
                    self._binding.get(mode) == WATER_TEMP_BINDING_INTERLOCK or self._interlock.just_cleared
                )
                await self._async_write(mode, entity_id, value, now=now, force=interlocked)
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
        return configured_ramp_start(mode, config)

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
        state = self.hass.states.get(entity_id)
        if state is None:
            # Entity not loaded yet (renamed, still starting up, etc.) --
            # skip this write rather than clamping against the
            # heating-shaped SUPPLY_TEMP_MIN/MAX fallback (25/80), which
            # would poison _last_written with a bogus value (review finding
            # #4). The 5-minute timer retries once the entity is available.
            _LOGGER.debug("Water temp control: %s has no state yet, skipping write", entity_id)
            return False

        minimum, maximum, step = entity_limits(state)
        rounded = round_safe(value, mode, step)
        final = min(max(rounded, minimum), maximum)

        if entity_limit_binds(mode, rounded, minimum, maximum):
            # Review finding #5: an entity limit that clamps *past* the
            # computed target in the unsafe direction must not be silent.
            self._binding[mode] = WATER_TEMP_BINDING_ENTITY_LIMIT
            warn_entity_limited(
                self._last_entity_limit_warned, mode, entity_id, rounded, final, now, WATER_TEMP_WARN_INTERVAL_SECONDS
            )

        last = self._last_written.get(entity_id)
        # Compare the post-clamp, post-round value: comparing the raw value
        # would re-issue identical calls forever when the target is out of range.
        if last is not None and abs(final - last) < 1e-6:
            self._pending.pop(entity_id, None)
            return False

        if not force and last is not None and not is_safe_direction(mode, final, last):
            pending = self._pending.get(entity_id)
            if pending is None:
                self._pending[entity_id] = (final, now)
                return False

            extreme_value, drift_started_at = pending
            # Track the running most-unsafe extreme since the anchor, not
            # just the previous candidate (finding N3) -- otherwise any
            # safe-direction blip resets the dwell and a genuinely
            # trending-but-noisy target never accumulates held time.
            if is_safe_direction(mode, extreme_value, final):
                extreme_value = final

            # A reversal (finding #6/N3) only counts once final has moved
            # back toward safety from that extreme by more than one entity
            # step; anything less is noise, not a genuine direction change.
            if is_safe_direction(mode, final, extreme_value) and abs(final - extreme_value) > step + 1e-9:
                self._pending[entity_id] = (final, now)
                return False

            self._pending[entity_id] = (extreme_value, drift_started_at)
            if (now - drift_started_at).total_seconds() < self._min_write_interval:
                return False

        if not await self._async_call_set_value(entity_id, final, now):
            return False

        self._pending.pop(entity_id, None)
        if last is not None and abs(final - last) >= WATER_TEMP_GATE_WRITE_DELTA:
            self._gate_until[mode] = now + timedelta(minutes=WATER_TEMP_SETTLING_MINUTES)
        self._last_written[entity_id] = final
        return True

    async def _async_call_set_value(self, entity_id: str, value: float, now: datetime) -> bool:
        """Call ``set_value`` on the target entity, retrying (rate-limited
        error log) via :class:`HeaterServiceCaller`-style handling."""
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

    # ── timers ───────────────────────────────────────────────────────────────

    def async_start(self) -> None:
        """Register the startup compute and 5-min recompute interval (sync, for ``coordinator.__init__``)."""
        self._started_unsub = self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self._async_on_ha_started)
        self._interval_unsub = async_track_time_interval(
            self.hass,
            self._async_timer_tick,
            timedelta(seconds=WATER_TEMP_UPDATE_INTERVAL_SECONDS),
        )
        _LOGGER.debug("Water temp control: timers registered")

    def async_cleanup(self) -> None:
        """Cancel every registered listener.  Called from coordinator cleanup."""
        for name in ("_started_unsub", "_startup_unsub", "_interval_unsub"):
            unsub = getattr(self, name)
            if unsub is not None:
                unsub()
                setattr(self, name, None)
        _LOGGER.debug("Water temp control: timers cancelled")

    async def _async_on_ha_started(self, _event: Any) -> None:
        """Schedule the first computation after a short startup delay."""
        self._started_unsub = None
        self._startup_unsub = async_call_later(self.hass, WATER_TEMP_STARTUP_DELAY_SECONDS, self._async_startup_compute)

    async def _async_startup_compute(self, _now: Any) -> None:
        """Run the first computation once zones have registered and state restored."""
        self._startup_unsub = None
        await self._async_timer_tick(None)

    async def _async_timer_tick(self, _now: Any) -> None:
        """Timer body — one bad cycle must never kill the interval."""
        try:
            await self.async_apply(self._utcnow())
        except Exception:  # broad: keep the timer alive
            _LOGGER.exception("Water temp control: computation cycle failed")

    # ── learning gate ────────────────────────────────────────────────────────

    def learning_gate(self, mode: str | None) -> bool:
        """Return True while learning must be suppressed for ``mode``.

        Water-temp changes move the plant gain under the adaptive learner
        (zone gain ~ T_room - T_water); a multi-day ramp looks exactly like
        the UndershootDetector failure signature. True while a ramp is
        active for ``mode`` (HVAC state or internal key), or within one
        settling window of a write that moved the value by >= 1.0 °C.
        """
        key = self._normalize_mode(mode)
        if key is None or key not in self.enabled_modes:
            return False

        if self._ramp[key].ramp_started is not None:
            return True

        until = self._gate_until.get(key)
        return until is not None and self._utcnow() < until

    @staticmethod
    def _normalize_mode(mode: str | None) -> str | None:
        """Map an HVAC state or internal key to an internal mode key."""
        if mode in (WATER_TEMP_MODE_COOLING, WATER_TEMP_MODE_HEATING):
            return mode
        if mode == "cool":
            return WATER_TEMP_MODE_COOLING
        if mode == "heat":
            return WATER_TEMP_MODE_HEATING
        return None

    # ── diagnostics ──────────────────────────────────────────────────────────

    def diagnostics(self) -> dict[str, Any]:
        """Return the diagnostic sensor payload."""
        mode: str | None = None
        for candidate in (WATER_TEMP_MODE_COOLING, WATER_TEMP_MODE_HEATING):
            if candidate in self._effective:
                mode = candidate
                break

        if mode is None:
            return {
                "mode": None,
                "effective": None,
                "dew_point": self._last_scan.dew_point if self._last_scan else None,
                "binding_constraint": None,
                "ramp_active": False,
                "days_remaining": None,
                "worst_source": self._last_scan.worst_source if self._last_scan else None,
            }

        ramp = self._ramp[mode]
        return {
            "mode": mode,
            "effective": self._effective.get(mode),
            "dew_point": self._last_scan.dew_point if self._last_scan else None,
            "binding_constraint": self._binding.get(mode),
            "ramp_active": ramp.ramp_started is not None,
            "days_remaining": self._days_remaining(mode),
            "worst_source": self._last_scan.worst_source if self._last_scan else None,
        }

    def _days_remaining(self, mode: str) -> float | None:
        """Return days left on an active ramp, or None."""
        ramp = self._ramp[mode]
        if ramp.ramp_started is None:
            return None
        current = self._effective.get(mode)
        if current is None:
            return None

        config = self._heating if mode == WATER_TEMP_MODE_HEATING else self._cooling
        rate = configured_ramp_rate(mode, config)
        if rate <= 0:
            return None

        if mode == WATER_TEMP_MODE_HEATING:
            if self._heating_target is None:
                return None
            remaining = self._heating_target - current
        else:
            floor = float((config or {}).get(CONF_WATER_TEMP_MIN_SUPPLY_TEMP, DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP))
            dew_target = floor
            if self._last_scan is not None and self._last_scan.dew_point is not None and not self._last_scan.blind:
                margin = float(
                    (config or {}).get(CONF_WATER_TEMP_DEW_POINT_MARGIN, DEFAULT_WATER_TEMP_DEW_POINT_MARGIN)
                )
                dew_target = max(self._last_scan.dew_point + margin, floor)
            remaining = current - dew_target

        return round(max(0.0, remaining) / rate, 2)
