"""PID service methods for adaptive thermostat.

This module contains all PID-related service call handlers: setting PID parameters,
resetting to physics defaults, applying adaptive recommendations, managing learning,
rolling back gains, managing PID history, and auto-apply evaluation.
"""

from __future__ import annotations

import logging

from homeassistant.components.climate import HVACMode
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from .const import PIDChangeReason

_LOGGER = logging.getLogger(__name__)


class ClimatePIDServicesMixin:
    """Mixin providing PID service call handlers for AdaptiveThermostat.

    Encapsulates service methods for PID parameter management, adaptive learning
    application, history management, and auto-apply evaluation.
    """

    async def async_set_pid(self, **kwargs):
        """Set PID parameters.

        Delegates to PIDTuningManager for the actual implementation.
        """
        await self._pid_tuning_manager.async_set_pid(**kwargs)

    async def async_set_pid_mode(self, **kwargs):
        """Set PID mode (AUTO or OFF).

        Delegates to PIDTuningManager for the actual implementation.
        """
        await self._pid_tuning_manager.async_set_pid_mode(**kwargs)

    async def async_set_preset_temp(self, **kwargs):
        """Set the presets modes temperatures."""
        await self._temperature_manager.async_set_preset_temp(**kwargs)

    async def clear_integral(self, **kwargs):
        """Clear the integral value."""
        await self.async_set_integral(0.0)

    async def async_set_integral(self, value: float) -> None:
        """Set the PID integral term under lock to avoid racing the control loop (L17).

        Callers (event handlers, service calls) must use this instead of writing
        ``_pid_controller.integral`` directly so the mutation is serialised with
        ``_async_control_heating``, which holds ``_temp_lock`` while reading the integral.
        """
        async with self._temp_lock:
            if self._pid_controller is not None:  # pyright: ignore[reportUnnecessaryComparison]
                if self._gains_manager is not None:
                    self._gains_manager.set_integral(value, PIDChangeReason.SERVICE_CALL)
                    self._i = self._pid_controller.integral  # sync to clamped value
                else:
                    self._pid_controller.integral = value
                    self._i = value
        self.async_write_ha_state()

    async def async_reset_pid_to_physics(self, **kwargs):
        """Reset PID values to physics-based defaults.

        Delegates to PIDTuningManager for the actual implementation.
        """
        await self._pid_tuning_manager.async_reset_pid_to_physics(**kwargs)

    async def async_apply_adaptive_pid(self, **kwargs):
        """Apply adaptive PID values based on learned metrics.

        Delegates to PIDTuningManager for the actual implementation.
        """
        await self._pid_tuning_manager.async_apply_adaptive_pid(**kwargs)

    async def async_apply_adaptive_ke(self, **kwargs):
        """Apply adaptive Ke value based on learned outdoor temperature correlations.

        Delegates to PIDTuningManager (which delegates to KeManager) for the actual implementation.
        """
        if self._ke_controller is not None:
            await self._ke_controller.async_apply_adaptive_ke(**kwargs)

    async def async_clear_learning(self, **kwargs):
        """Clear all learning data and reset PID to physics defaults.

        Delegates to PIDTuningManager for the actual implementation.
        """
        await self._pid_tuning_manager.async_clear_learning(**kwargs)

    async def async_rollback_pid(self, **kwargs):
        """Rollback PID to previous configuration.

        Service call handler for rollback_pid.
        Delegates to PIDTuningManager for the actual implementation.
        """
        await self._pid_tuning_manager.async_rollback_pid()

    async def async_delete_pid_history(self, indices: list[int], mode: str = "heat") -> None:
        """Delete specific entries from PID history.

        Args:
            indices: List of 0-based indices to delete
            mode: "heat" or "cool"
        """
        hvac_mode = HVACMode.COOL if mode.lower() == "cool" else HVACMode.HEAT
        self._gains_manager.delete_history_entries(indices, hvac_mode)
        self.async_write_ha_state()

    async def async_restore_pid_history(self, index: int, mode: str = "heat") -> None:
        """Restore PID gains from a specific history entry.

        Args:
            index: 0-based index of history entry
            mode: "heat" or "cool"
        """
        hvac_mode = HVACMode.COOL if mode.lower() == "cool" else HVACMode.HEAT
        self._gains_manager.restore_from_history(index, hvac_mode)
        self.async_write_ha_state()

    async def _check_auto_apply_pid(self) -> None:
        """Check and potentially auto-apply adaptive PID recommendations.

        Called after each cycle finalization when auto_apply_pid is enabled.
        Obtains outdoor temperature from sensor state if available and triggers
        auto-apply evaluation through PIDTuningManager.
        """
        if not self._auto_apply_pid or not self._pid_tuning_manager:
            return

        # Get outdoor temperature from sensor state if available
        outdoor_temp = None
        if self._ext_sensor_entity_id is not None:
            ext_sensor_state = self.hass.states.get(self._ext_sensor_entity_id)
            if ext_sensor_state and ext_sensor_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    outdoor_temp = float(ext_sensor_state.state)
                except (ValueError, TypeError):
                    pass
        elif self._ext_temp is not None:
            outdoor_temp = self._ext_temp

        result = await self._pid_tuning_manager.async_auto_apply_adaptive_pid(outdoor_temp, mode=self._hvac_mode)

        if result.get("applied"):
            old_values = result.get("old_values", {})
            new_values = result.get("new_values", {})

            try:
                _old_kp = float(old_values.get("kp", 0.0))
                _old_ki = float(old_values.get("ki", 0.0))
                _old_kd = float(old_values.get("kd", 0.0))
                _new_kp = float(new_values.get("kp", 0.0))
                _new_ki = float(new_values.get("ki", 0.0))
                _new_kd = float(new_values.get("kd", 0.0))
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "notification_id": f"adaptive_climate_auto_apply_{self._zone_id}",
                        "title": f"🔧 PID Auto-Applied: {self._name}",
                        "message": (
                            f"Adaptive PID values have been automatically applied.\n\n"
                            f"**Previous values:**\n"
                            f"- Kp: {_old_kp:.4f}\n"
                            f"- Ki: {_old_ki:.5f}\n"
                            f"- Kd: {_old_kd:.3f}\n\n"
                            f"**New values:**\n"
                            f"- Kp: {_new_kp:.4f}\n"
                            f"- Ki: {_new_ki:.5f}\n"
                            f"- Kd: {_new_kd:.3f}\n\n"
                            f"The system will validate performance over the next 5 cycles. "
                            f"If performance degrades, it will automatically rollback.\n\n"
                            f"To manually rollback, call service: "
                            f"`adaptive_climate.rollback_pid`"
                        ),
                    },
                    blocking=False,
                )
            except Exception as _notify_err:
                _LOGGER.error(
                    "%s: Failed to send auto-apply notification: %s (old=%s, new=%s)",
                    self.entity_id,
                    _notify_err,
                    old_values,
                    new_values,
                )
            _LOGGER.info(
                "%s: Auto-applied PID values: Kp=%.4f→%.4f, Ki=%.5f→%.5f, Kd=%.3f→%.3f",
                self.entity_id,
                old_values.get("kp", 0),
                new_values.get("kp", 0),
                old_values.get("ki", 0),
                new_values.get("ki", 0),
                old_values.get("kd", 0),
                new_values.get("kd", 0),
            )
