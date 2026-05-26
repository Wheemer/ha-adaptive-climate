"""Test PWM + climate entity validation."""

import pytest
import voluptuous as vol
from datetime import timedelta
from unittest.mock import patch

from custom_components.adaptive_climate.const import CONF_HEATER, CONF_COOLER, CONF_PWM
from custom_components.adaptive_climate.climate_setup import validate_pwm_compatibility


def _mock_split_entity_id(entity_id: str) -> tuple[str, str]:
    """Mock split_entity_id to avoid HA dependency."""
    if "." in entity_id:
        return tuple(entity_id.split(".", 1))
    return ("", "")


@pytest.fixture(autouse=True)
def mock_split_entity_id():
    """Auto-use fixture to mock split_entity_id for all tests."""
    with patch(
        "custom_components.adaptive_climate.climate_setup.split_entity_id",
        side_effect=_mock_split_entity_id,
    ):
        yield


class TestPWMClimateValidation:
    """Test suite for PWM climate entity validation."""

    def test_valid_pwm_with_switch(self):
        """Test that PWM mode works with switch entities."""
        config = {
            CONF_HEATER: ["switch.heater"],
            CONF_PWM: timedelta(minutes=15),
        }
        # Should not raise
        result = validate_pwm_compatibility(config)
        assert result == config

    def test_valid_pwm_with_light(self):
        """Test that PWM mode works with light entities."""
        config = {
            CONF_HEATER: ["light.heater"],
            CONF_PWM: timedelta(minutes=10),
        }
        # Should not raise
        result = validate_pwm_compatibility(config)
        assert result == config

    def test_valid_valve_mode_with_climate(self):
        """Test that valve mode (PWM=0) works with climate entities."""
        config = {
            CONF_HEATER: ["climate.underfloor"],
            CONF_PWM: timedelta(seconds=0),
        }
        # Should not raise
        result = validate_pwm_compatibility(config)
        assert result == config

    def test_valid_no_pwm_specified(self):
        """Test that no PWM works with climate entities."""
        config = {
            CONF_HEATER: ["climate.underfloor"],
        }
        # Should not raise (no PWM key)
        result = validate_pwm_compatibility(config)
        assert result == config

    def test_invalid_pwm_with_climate_heater(self):
        """Test that PWM mode raises error with climate heater."""
        config = {
            CONF_HEATER: ["climate.underfloor"],
            CONF_PWM: timedelta(minutes=15),
        }
        with pytest.raises(vol.Invalid) as exc_info:
            validate_pwm_compatibility(config)

        assert "climate.underfloor" in str(exc_info.value)
        assert "nested control loops" in str(exc_info.value)
        assert "pwm to '00:00:00'" in str(exc_info.value)

    def test_invalid_pwm_with_climate_cooler(self):
        """Test that PWM mode raises error with climate cooler."""
        config = {
            CONF_COOLER: ["climate.ac_unit"],
            CONF_PWM: timedelta(minutes=10),
        }
        with pytest.raises(vol.Invalid) as exc_info:
            validate_pwm_compatibility(config)

        assert "climate.ac_unit" in str(exc_info.value)
        assert "nested control loops" in str(exc_info.value)

    def test_invalid_pwm_with_multiple_climate_entities(self):
        """Test that PWM mode raises error with multiple climate entities."""
        config = {
            CONF_HEATER: ["climate.zone1", "climate.zone2"],
            CONF_PWM: timedelta(minutes=15),
        }
        # Should raise on first climate entity found
        with pytest.raises(vol.Invalid) as exc_info:
            validate_pwm_compatibility(config)

        assert "climate." in str(exc_info.value)
        assert "nested control loops" in str(exc_info.value)

    def test_valid_mixed_entities_with_pwm(self):
        """Test that PWM works with mixed entity types (switches with PWM)."""
        # This config has switches with PWM, which is valid
        config = {
            CONF_HEATER: ["switch.heater", "switch.pump"],
            CONF_PWM: timedelta(minutes=15),
        }
        # Should not raise
        result = validate_pwm_compatibility(config)
        assert result == config

    def test_error_message_suggests_solutions(self):
        """Test that error message provides helpful solutions."""
        config = {
            CONF_HEATER: ["climate.radiant_floor"],
            CONF_PWM: timedelta(minutes=20),
        }
        with pytest.raises(vol.Invalid) as exc_info:
            validate_pwm_compatibility(config)

        error_msg = str(exc_info.value)
        # Check both solution suggestions are present
        assert "Set pwm to '00:00:00'" in error_msg or "valve mode" in error_msg
        assert "Use a switch" in error_msg or "switch/light entity" in error_msg

    def test_pwm_climate_validation_module_exists(self):
        """Marker test to verify module and function exist."""
        assert validate_pwm_compatibility is not None
        assert callable(validate_pwm_compatibility)
