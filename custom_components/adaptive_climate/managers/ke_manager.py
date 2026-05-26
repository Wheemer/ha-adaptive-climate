"""Ke (outdoor temperature compensation) learning manager for Adaptive Climate integration.

D5 (2026-05-26): Removed all backward-compatibility callback parameters and
dual-mode (state vs. callbacks) logic.  KeManager now accepts only a
KeManagerState Protocol instance for read-only state access; action callbacks
(async_control_heating, async_write_ha_state) remain as explicit callables.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Awaitable, Callable

# These imports are only needed when running in Home Assistant
try:
    from homeassistant.components.climate import HVACMode

    HAS_HOMEASSISTANT = True
except ImportError:
    HAS_HOMEASSISTANT = False
    HVACMode = Any

from ..adaptive.ke_learning import KeLearner
from .. import const
from ..const import PIDChangeReason

if TYPE_CHECKING:
    from ..protocols import KeManagerState
    from .pid_gains_manager import PIDGainsManager

_LOGGER = logging.getLogger(__name__)


class KeManager:
    """Manager for Ke (outdoor temperature compensation) learning.

    Manages the adaptive learning of the Ke parameter based on observed
    correlations between outdoor temperature and required heating effort.
    This includes:
    - Steady state detection
    - Ke observation recording
    - Ke adjustment calculation and application

    State is accessed exclusively through the KeManagerState Protocol; no
    direct thermostat references or lambda callbacks are accepted.
    """

    def __init__(
        self,
        state: KeManagerState,
        ke_learner: KeLearner | None = None,
        gains_manager: PIDGainsManager | None = None,
        async_control_heating: Callable[..., Awaitable[None]] | None = None,
        async_write_ha_state: Callable[[], Any] | None = None,
    ):
        """Initialize the KeManager.

        Args:
            state: KeManagerState protocol for all read-only state queries.
            ke_learner: KeLearner instance (may be None if no outdoor sensor).
            gains_manager: PIDGainsManager for centralized gain mutations and
                history recording.  When None, Ke changes are logged but not
                persisted to history.
            async_control_heating: Async callback to trigger heating control.
            async_write_ha_state: Async callback to write HA state.
        """
        self._state = state
        self._ke_learner = ke_learner
        self._gains_manager = gains_manager
        self._async_control_heating = async_control_heating
        self._async_write_ha_state = async_write_ha_state

        # Monotonic timestamps — reset on every process restart (see restore_state)
        self._steady_state_start: float | None = None
        self._last_ke_observation_time: float | None = None

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def ke_learner(self) -> KeLearner | None:
        """Return the KeLearner instance."""
        return self._ke_learner

    @property
    def steady_state_start(self) -> float | None:
        """Return the timestamp when steady state began."""
        return self._steady_state_start

    @property
    def last_ke_observation_time(self) -> float | None:
        """Return the timestamp of the last Ke observation."""
        return self._last_ke_observation_time

    def update_ke_learner(self, ke_learner: KeLearner | None) -> None:
        """Replace the KeLearner instance (e.g. after outdoor sensor change).

        Args:
            ke_learner: New KeLearner instance, or None to disable Ke learning.
        """
        self._ke_learner = ke_learner

    def get_learner_dict(self) -> dict | None:
        """Return the KeLearner serialized dict, or None if no learner is set.

        Used by CycleMetricsRecorder to include ke_data in the periodic
        learning save so Ke observations survive restarts (M07).
        """
        if self._ke_learner is None:
            return None
        return self._ke_learner.to_dict()

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def is_at_steady_state(self) -> bool:
        """Check if the system is at steady state (maintaining target temperature).

        Steady state is determined by:
        1. Temperature within tolerance of target
        2. Maintained for KE_STEADY_STATE_DURATION minutes
        3. HVAC mode is active (not OFF)

        Returns:
            True if at steady state, False otherwise
        """
        if self._state._hvac_mode == HVACMode.OFF:
            self._steady_state_start = None
            return False

        current_temp = self._state.current_temperature
        target_temp = self._state.target_temperature

        if current_temp is None or target_temp is None:
            self._steady_state_start = None
            return False

        # Check if within tolerance band
        tolerance = max(self._state._cold_tolerance, self._state._hot_tolerance, 0.2)
        if abs(current_temp - target_temp) > tolerance:
            self._steady_state_start = None
            return False

        # Start tracking steady state if not already
        current_time = time.monotonic()
        if self._steady_state_start is None:
            self._steady_state_start = current_time

        # Check if we've maintained steady state long enough
        steady_duration_seconds = current_time - self._steady_state_start
        required_duration_seconds = const.KE_STEADY_STATE_DURATION * 60

        return steady_duration_seconds >= required_duration_seconds

    def maybe_record_observation(self) -> None:
        """Record a Ke observation if conditions are met.

        Conditions:
        1. Ke learner exists and is enabled (or becomes enabled when PID converges)
        2. System is at steady state
        3. Outdoor temperature sensor is available
        4. Minimum time has passed since last observation (5 minutes)
        """
        if not self._ke_learner:
            return

        entity_id = self._state.entity_id

        # Check if PID has converged and enable Ke learning if not already enabled
        if not self._ke_learner.enabled:
            if self._state.is_pid_converged_for_ke():
                # PID has converged — enable Ke learning and apply physics-based Ke
                self._ke_learner.enable()
                physics_ke = self._ke_learner.current_ke
                if physics_ke > 0:
                    if self._gains_manager:
                        self._gains_manager.set_gains(
                            PIDChangeReason.KE_PHYSICS,
                            ke=physics_ke,
                        )
                    _LOGGER.info(
                        "%s: PID converged - enabled Ke learning and applied physics-based Ke=%.3f",
                        entity_id,
                        physics_ke,
                    )
            else:
                # PID not converged yet, skip observation
                return

        if not self.is_at_steady_state():
            return

        ext_temp = self._state._ext_temp
        if ext_temp is None:
            return

        # Rate limit: at least 5 minutes between observations
        current_time = time.monotonic()
        if self._last_ke_observation_time is not None:
            if current_time - self._last_ke_observation_time < 300:  # 5 minutes
                return

        # Record the observation
        control_output = self._state._control_output
        current_temp = self._state.current_temperature
        target_temp = self._state.target_temperature

        self._ke_learner.add_observation(
            outdoor_temp=ext_temp,
            pid_output=control_output,
            indoor_temp=float(current_temp),  # type: ignore[arg-type]
            target_temp=float(target_temp),  # type: ignore[arg-type]
        )
        self._last_ke_observation_time = current_time

        _LOGGER.debug(
            "%s: Ke observation recorded: outdoor=%.1f, pid=%.1f, indoor=%.1f, target=%.1f",
            entity_id,
            ext_temp,
            control_output,
            current_temp,
            target_temp,
        )

    async def async_apply_adaptive_ke(self, **kwargs: object) -> None:
        """Apply adaptive Ke value based on learned outdoor temperature correlations."""
        entity_id = self._state.entity_id

        if not self._ke_learner:
            _LOGGER.warning("%s: Cannot apply adaptive Ke - no Ke learner (outdoor sensor not configured?)", entity_id)
            return

        if not self._ke_learner.enabled:
            _LOGGER.warning("%s: Cannot apply adaptive Ke - learning not enabled (PID not converged yet)", entity_id)
            return

        recommendation = self._ke_learner.calculate_ke_adjustment()

        if recommendation is None:
            summary = self._ke_learner.get_observations_summary()
            _LOGGER.warning(
                "%s: Insufficient data for adaptive Ke (observations: %d, temp_range: %s, correlation: %s)",
                entity_id,
                summary.get("count", 0),
                summary.get("outdoor_temp_range"),
                summary.get("correlation"),
            )
            return

        old_ke = self._state._ke
        self._ke_learner.apply_ke_adjustment(recommendation)

        if self._gains_manager:
            self._gains_manager.set_gains(
                PIDChangeReason.KE_LEARNING,
                ke=recommendation,
            )

        _LOGGER.info("%s: Applied adaptive Ke: %.2f (was %.2f)", entity_id, recommendation, old_ke)

        if self._async_control_heating:
            await self._async_control_heating(calc_pid=True)
        if self._async_write_ha_state:
            await self._async_write_ha_state()

    def restore_state(
        self,
        steady_state_start: float | None = None,
        last_ke_observation_time: float | None = None,
    ) -> None:
        """Restore state from saved data.

        Both timestamp parameters are accepted for call-site compatibility but are
        intentionally ignored: monotonic timestamps are meaningless after a process
        restart, so tracking always restarts fresh on the next temperature update.

        Args:
            steady_state_start: Ignored.
            last_ke_observation_time: Ignored.
        """
        _ = steady_state_start
        _ = last_ke_observation_time
        self._steady_state_start = None
        self._last_ke_observation_time = None
