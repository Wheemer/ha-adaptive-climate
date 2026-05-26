"""Tests for climate_setup module - configuration schema and platform setup."""

from __future__ import annotations

import pytest
from datetime import timedelta
from unittest.mock import Mock, AsyncMock, patch
import voluptuous as vol

from custom_components.adaptive_climate.climate_setup import (
    validate_pwm_compatibility,
    _resolve_pwm,
)
from custom_components.adaptive_climate.const import (
    CONF_VALVE_ACTUATION_TIME,
    CONF_HEATER,
    CONF_COOLER,
    CONF_PWM,
    HEATING_TYPE_FLOOR_HYDRONIC,
    HEATING_TYPE_RADIATOR,
    HEATING_TYPE_CONVECTOR,
    HEATING_TYPE_FORCED_AIR,
    HEATING_TYPE_VALVE_DEFAULTS,
)


class TestValveActuationTimeDefaults:
    """Test valve_actuation_time default values from heating type constants."""

    def test_floor_hydronic_default(self):
        """Test floor_hydronic uses 120 second default."""
        assert HEATING_TYPE_VALVE_DEFAULTS[HEATING_TYPE_FLOOR_HYDRONIC] == 120

    def test_radiator_default(self):
        """Test radiator uses 90 second default."""
        assert HEATING_TYPE_VALVE_DEFAULTS[HEATING_TYPE_RADIATOR] == 90

    def test_convector_default(self):
        """Test convector uses 0 second default (no valve delay)."""
        assert HEATING_TYPE_VALVE_DEFAULTS[HEATING_TYPE_CONVECTOR] == 0

    def test_forced_air_default(self):
        """Test forced_air uses 30 second default."""
        assert HEATING_TYPE_VALVE_DEFAULTS[HEATING_TYPE_FORCED_AIR] == 30


class TestPWMValidation:
    """Test PWM compatibility validation."""

    @patch("custom_components.adaptive_climate.climate_setup.split_entity_id")
    def test_pwm_with_switch_entity_allowed(self, mock_split):
        """Test PWM mode is allowed with switch entities."""
        mock_split.return_value = ("switch", "heater")

        config = {
            CONF_HEATER: ["switch.heater"],
            CONF_PWM: timedelta(minutes=15),
        }

        # Should not raise
        validated = validate_pwm_compatibility(config)
        assert validated == config

    @patch("custom_components.adaptive_climate.climate_setup.split_entity_id")
    def test_pwm_with_climate_entity_rejected(self, mock_split):
        """Test PWM mode is rejected with climate entities."""
        mock_split.return_value = ("climate", "zone_valve")

        config = {
            CONF_HEATER: ["climate.zone_valve"],
            CONF_PWM: timedelta(minutes=15),
        }

        # Should raise vol.Invalid
        with pytest.raises(vol.Invalid) as exc_info:
            validate_pwm_compatibility(config)

        assert "climate.zone_valve" in str(exc_info.value)
        assert "PWM mode cannot be used" in str(exc_info.value)

    @patch("custom_components.adaptive_climate.climate_setup.split_entity_id")
    def test_zero_pwm_with_climate_entity_allowed(self, mock_split):
        """Test PWM=0 (valve mode) is allowed with climate entities."""
        mock_split.return_value = ("climate", "zone_valve")

        config = {
            CONF_HEATER: ["climate.zone_valve"],
            CONF_PWM: timedelta(seconds=0),
        }

        # Should not raise
        validated = validate_pwm_compatibility(config)
        assert validated == config

    @patch("custom_components.adaptive_climate.climate_setup.split_entity_id")
    def test_no_pwm_with_climate_entity_allowed(self, mock_split):
        """Test missing PWM (default valve mode) is allowed with climate entities."""
        mock_split.return_value = ("climate", "zone_valve")

        config = {
            CONF_HEATER: ["climate.zone_valve"],
        }

        # Should not raise (no pwm key means pwm defaults later)
        validated = validate_pwm_compatibility(config)
        assert validated == config


class TestResolvePwm:
    """Test _resolve_pwm helper for None-aware PWM resolution."""

    def test_explicit_zero_entity_config_is_respected(self):
        """H01: explicit pwm=timedelta(0) must not fall through to 15-min default."""
        result = _resolve_pwm(timedelta(seconds=0), None)
        assert result == timedelta(seconds=0), "timedelta(0) is falsy but valid — must NOT fall through to default"

    def test_explicit_nonzero_entity_config_wins(self):
        """Entity-level nonzero PWM overrides domain and default."""
        result = _resolve_pwm(timedelta(minutes=10), timedelta(minutes=5))
        assert result == timedelta(minutes=10)

    def test_entity_config_none_falls_through_to_domain(self):
        """When entity config is absent, domain PWM is used."""
        result = _resolve_pwm(None, timedelta(minutes=5))
        assert result == timedelta(minutes=5)

    def test_domain_zero_is_respected(self):
        """Domain-level zero PWM must not fall through to default either."""
        result = _resolve_pwm(None, timedelta(seconds=0))
        assert result == timedelta(seconds=0)

    def test_both_none_returns_default(self):
        """When both entity and domain configs are None, returns 15-min default."""
        result = _resolve_pwm(None, None)
        assert result == timedelta(minutes=15)
