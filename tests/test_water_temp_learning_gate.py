"""Tests for water-temp learning suppression across the thermostat surface."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.adaptive_climate.managers.pause_detector import PauseDetector


class FakeEntity:
    """Minimal thermostat-like object for PauseDetector.from_entity."""

    def __init__(self, water_temp_gate=False):
        self._night_setback_controller = None
        self._contact_sensor_handler = None
        self._humidity_detector = None
        self.water_temp_learning_gate_active = water_temp_gate


class TestPauseDetectorGate:
    def test_learning_is_paused_while_the_gate_is_open(self):
        assert PauseDetector(water_temp_gate=True).is_learning_paused() is True

    def test_learning_is_not_paused_when_the_gate_is_closed(self):
        assert PauseDetector(water_temp_gate=False).is_learning_paused() is False

    def test_from_entity_picks_up_the_gate_flag(self):
        assert PauseDetector.from_entity(FakeEntity(True)).is_learning_paused() is True
        assert PauseDetector.from_entity(FakeEntity(False)).is_learning_paused() is False

    def test_from_entity_defaults_to_false_for_objects_without_the_property(self):
        assert PauseDetector.from_entity(object()).is_learning_paused() is False

    def test_control_is_not_paused_by_the_water_temp_gate(self):
        """The gate suppresses learning, not the actuator."""
        assert PauseDetector(water_temp_gate=True).is_control_paused("cool") is False


class TestThermostatGateProperty:
    @staticmethod
    def _thermostat(gate_value, hvac_mode="cool"):
        from custom_components.adaptive_climate.climate import AdaptiveThermostat

        thermostat = AdaptiveThermostat.__new__(AdaptiveThermostat)
        thermostat._hvac_mode = hvac_mode
        thermostat._night_setback_controller = None
        coordinator = MagicMock()
        coordinator.water_temp_learning_gate = MagicMock(return_value=gate_value)
        thermostat.hass = MagicMock()
        thermostat.hass.data = {"adaptive_climate": {"coordinator": coordinator}}
        return thermostat, coordinator

    def test_property_delegates_to_the_coordinator_with_the_current_mode(self):
        thermostat, coordinator = self._thermostat(True, hvac_mode="cool")

        assert thermostat.water_temp_learning_gate_active is True
        coordinator.water_temp_learning_gate.assert_called_once_with("cool")

    def test_property_is_false_without_a_coordinator(self):
        from custom_components.adaptive_climate.climate import AdaptiveThermostat

        thermostat = AdaptiveThermostat.__new__(AdaptiveThermostat)
        thermostat._hvac_mode = "cool"
        thermostat.hass = MagicMock()
        thermostat.hass.data = {}

        assert thermostat.water_temp_learning_gate_active is False

    def test_grace_period_is_true_while_the_gate_is_open(self):
        """This is the hook CycleMetricsRecorder reads to skip cycle recording."""
        thermostat, _ = self._thermostat(True)

        assert thermostat.in_learning_grace_period is True

    def test_grace_period_still_reflects_night_setback_when_the_gate_is_closed(self):
        thermostat, _ = self._thermostat(False)
        night_setback = MagicMock()
        night_setback.in_learning_grace_period = True
        thermostat._night_setback_controller = night_setback

        assert thermostat.in_learning_grace_period is True

    def test_grace_period_is_false_when_neither_source_is_active(self):
        thermostat, _ = self._thermostat(False)
        night_setback = MagicMock()
        night_setback.in_learning_grace_period = False
        thermostat._night_setback_controller = night_setback

        assert thermostat.in_learning_grace_period is False


class TestUndershootSuppression:
    def test_undershoot_update_is_gated_on_the_water_temp_flag(self):
        """The guard in climate_control must include the gate flag."""
        import inspect

        from custom_components.adaptive_climate import climate_control

        source = inspect.getsource(climate_control)
        assert "not self.water_temp_learning_gate_active" in source
