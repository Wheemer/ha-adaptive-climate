"""Cooling interlock state machine for water temperature control.

Split out of ``water_temp_controller.py`` to keep that module under the
project's 800-line ceiling.  Forces an immediate park at the safer of
``ramp_start`` / the current dew target while the condensation sensor is ON
or any COOL zone reports an ``open_window`` / ``contact_open`` override, and
holds for a stabilization window after the condition clears.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from ..const import WATER_TEMP_INTERLOCK_STABILIZATION_SECONDS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..coordinator import AdaptiveThermostatCoordinator
    from .water_temp_controller import ModeRampState


class CoolingInterlockManager:
    """Evaluate and track the cooling interlock across compute cycles."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: AdaptiveThermostatCoordinator,
        condensation_sensor: str | None,
        cool_hvac_state: str,
    ) -> None:
        """Initialize the interlock manager.

        Args:
            hass: Home Assistant instance.
            coordinator: Zone registry, used for COOL-zone override checks.
            condensation_sensor: Optional ``binary_sensor`` entity id.
            cool_hvac_state: The HVAC state string that means "cooling"
                (``"cool"``).
        """
        self._hass = hass
        self._coordinator = coordinator
        self._condensation_sensor = condensation_sensor
        self._cool_hvac_state = cool_hvac_state

        self._engaged = False
        self._cleared_at: datetime | None = None
        self._engaged_at: datetime | None = None
        self.just_cleared = False

    def evaluate(self, now: datetime, ramp: ModeRampState) -> bool:
        """Advance the state machine and return whether it's holding.

        True while the condensation sensor is ON or any COOL zone reports an
        ``open_window`` / ``contact_open`` override, and for
        :data:`WATER_TEMP_INTERLOCK_STABILIZATION_SECONDS` after the last
        such condition clears.

        On the cycle the interlock clears, advances ``ramp.ramp_started``
        and ``ramp.last_active`` by the duration the interlock was held
        (review finding #8) — while interlocked the target is parked, not
        progressing, so the held span must not count as ramp progress nor
        look like a seasonal idle gap once normal computation resumes.

        Args:
            now: Current wall-clock time.
            ramp: The cooling mode's ramp state, advanced on clear.
        """
        active = self._condition_active()
        self.just_cleared = False

        if active:
            if not self._engaged:
                self._engaged_at = now
            self._engaged = True
            self._cleared_at = None
            return True

        if not self._engaged:
            return False

        if self._cleared_at is None:
            self._cleared_at = now
        elapsed = (now - self._cleared_at).total_seconds()
        if elapsed < WATER_TEMP_INTERLOCK_STABILIZATION_SECONDS:
            return True

        self._engaged = False
        self._cleared_at = None
        # The stabilization window just elapsed: per spec ("resume normal
        # computation N min after the condition clears"), this cycle's
        # write must land immediately rather than restart a fresh dwell
        # timer stacked on top of the wait we already just observed.
        self.just_cleared = True
        self._advance_ramp(ramp, now)
        return False

    def reset(self) -> None:
        """Clear all bookkeeping when cooling itself is inactive.

        An interlock means nothing when no zone is cooling (review finding
        N1, BLOCKER): without this, an interlock engaged right as the
        season ends freezes ``_engaged_at`` — on the next season's resume,
        months later, the entire off-season gap would be read back as the
        interlock's own held duration, advancing ``last_active`` to ~now
        and masking the genuine idle gap that should restart the ramp.
        """
        self._engaged = False
        self._cleared_at = None
        self._engaged_at = None

    @staticmethod
    def park_value(ramp_start: float, dew_target: float) -> float:
        """Return the interlock park value: ``max(ramp_start, dew_target)``.

        An interlock must never park the supply *below* what condensation
        safety currently requires.
        """
        return max(ramp_start, dew_target)

    def _advance_ramp(self, ramp: ModeRampState, now: datetime) -> None:
        """Skip ``ramp`` forward by the held duration since it engaged."""
        engaged_at = self._engaged_at
        self._engaged_at = None
        if engaged_at is None:
            return

        duration = max(timedelta(0), now - engaged_at)
        if ramp.ramp_started is not None:
            ramp.ramp_started = min(ramp.ramp_started + duration, now)
        if ramp.last_active is not None:
            ramp.last_active = min(ramp.last_active + duration, now)

    def _condition_active(self) -> bool:
        """Return True while a raw interlock condition is present."""
        if self._condensation_sensor:
            state = self._hass.states.get(self._condensation_sensor)
            if state is not None and state.state == "on":
                return True

        for zone_data in self._coordinator.get_zones_in_mode(self._cool_hvac_state).values():
            climate_entity_id = zone_data.get("climate_entity_id")
            if not climate_entity_id:
                continue
            state = self._hass.states.get(climate_entity_id)
            if state is None:
                continue
            status = state.attributes.get("status") or {}
            for override in status.get("overrides", []) or []:
                if override.get("type") in ("open_window", "contact_open"):
                    return True

        return False
