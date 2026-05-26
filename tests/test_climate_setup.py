"""Tests for climate_setup module - configuration schema and platform setup."""

from __future__ import annotations

import pytest
from datetime import timedelta
from unittest.mock import patch
import voluptuous as vol

from custom_components.adaptive_climate.climate_setup import (
    validate_pwm_compatibility,
    _resolve_pwm,
)
from custom_components.adaptive_climate.const import (
    CONF_HEATER,
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


class TestSensorDiscoveryPayload:
    """H06: discovery payload must include heat-output sensor configuration."""

    @pytest.mark.asyncio
    async def test_discovery_payload_includes_heat_output_sensor_keys(self):
        """H06: When heat-output sensors are configured in hass.data, the sensor
        discovery payload from climate_setup must include supply_temp_sensor,
        return_temp_sensor, flow_rate_sensor and fallback_flow_rate so that
        HeatOutputSensor receives non-None references.
        """
        from unittest.mock import MagicMock, patch
        from custom_components.adaptive_climate.climate_setup import async_setup_platform
        from custom_components.adaptive_climate.const import DOMAIN

        mock_coordinator = MagicMock()
        mock_coordinator.register_zone = MagicMock()

        mock_store = MagicMock()
        mock_store.get_zone_data = MagicMock(return_value=None)

        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "learning_store": mock_store,
                "coordinator": mock_coordinator,
                "supply_temp_sensor": "sensor.supply_temp",
                "return_temp_sensor": "sensor.return_temp",
                "flow_rate_sensor": "sensor.flow_rate",
                "fallback_flow_rate": 1.5,
            }
        }
        hass.config.units.temperature_unit = "°C"

        config = {
            "name": "Test Zone",
            "heater": ["switch.test_heater"],
        }

        with (
            patch("custom_components.adaptive_climate.climate.AdaptiveThermostat"),
            patch("custom_components.adaptive_climate.thermostat_config.AdaptiveThermostatConfig"),
            patch("custom_components.adaptive_climate.climate_setup.AdaptiveLearner"),
            patch("custom_components.adaptive_climate.climate_setup.discovery") as mock_discovery,
            patch("custom_components.adaptive_climate.climate_setup.entity_platform") as mock_ep,
        ):
            mock_ep.current_platform.get.return_value = MagicMock()
            await async_setup_platform(hass, config, MagicMock())

        # discovery.async_load_platform must have been called (via hass.async_create_task)
        assert mock_discovery.async_load_platform.called, (
            "discovery.async_load_platform was never called — was coordinator missing?"
        )
        # Extract the discovery info dict (4th positional arg)
        call_args = mock_discovery.async_load_platform.call_args
        payload = call_args[0][3]

        assert payload.get("supply_temp_sensor") == "sensor.supply_temp", (
            f"Expected supply_temp_sensor='sensor.supply_temp', got {payload.get('supply_temp_sensor')!r}. "
            "H06: climate_setup discovery payload omits heat-output sensor keys."
        )
        assert payload.get("return_temp_sensor") == "sensor.return_temp"
        assert payload.get("flow_rate_sensor") == "sensor.flow_rate"
        assert payload.get("fallback_flow_rate") == 1.5

    @pytest.mark.asyncio
    async def test_discovery_payload_uses_default_flow_rate_when_not_configured(self):
        """H06 regression: fallback_flow_rate defaults to DEFAULT_FALLBACK_FLOW_RATE
        when not set in domain config (supply/return sensor keys are None).
        """
        from unittest.mock import MagicMock, patch
        from custom_components.adaptive_climate.climate_setup import async_setup_platform
        from custom_components.adaptive_climate.const import DOMAIN, DEFAULT_FALLBACK_FLOW_RATE

        mock_coordinator = MagicMock()
        mock_coordinator.register_zone = MagicMock()

        mock_store = MagicMock()
        mock_store.get_zone_data = MagicMock(return_value=None)

        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "learning_store": mock_store,
                "coordinator": mock_coordinator,
                # No heat-output sensor keys in domain data
            }
        }
        hass.config.units.temperature_unit = "°C"

        config = {
            "name": "Test Zone B",
            "heater": ["switch.test_heater"],
        }

        with (
            patch("custom_components.adaptive_climate.climate.AdaptiveThermostat"),
            patch("custom_components.adaptive_climate.thermostat_config.AdaptiveThermostatConfig"),
            patch("custom_components.adaptive_climate.climate_setup.AdaptiveLearner"),
            patch("custom_components.adaptive_climate.climate_setup.discovery") as mock_discovery,
            patch("custom_components.adaptive_climate.climate_setup.entity_platform") as mock_ep,
        ):
            mock_ep.current_platform.get.return_value = MagicMock()
            await async_setup_platform(hass, config, MagicMock())

        call_args = mock_discovery.async_load_platform.call_args
        payload = call_args[0][3]

        assert payload.get("supply_temp_sensor") is None
        assert payload.get("return_temp_sensor") is None
        assert payload.get("flow_rate_sensor") is None
        assert payload.get("fallback_flow_rate") == DEFAULT_FALLBACK_FLOW_RATE


class TestNumberPlatformDiscovery:
    """M02: number platform must be discovered for LearningWindowNumber to exist."""

    @pytest.mark.asyncio
    async def test_number_platform_loaded_on_first_zone_setup(self):
        """M02: discovery.async_load_platform('number') must be called once on first
        zone setup so LearningWindowNumber is created.
        """
        from unittest.mock import AsyncMock, MagicMock, patch
        from custom_components.adaptive_climate.climate_setup import async_setup_platform
        from custom_components.adaptive_climate.const import DOMAIN

        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock()
        mock_store.async_load_manifold_state = AsyncMock(return_value=None)

        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                # No learning_store yet — first zone setup
            }
        }
        hass.config.units.temperature_unit = "°C"

        config = {"name": "Test Zone"}  # No heater → early return after store creation

        with (
            patch(
                "custom_components.adaptive_climate.climate_setup.LearningDataStore",
                return_value=mock_store,
            ),
            patch("custom_components.adaptive_climate.climate_setup.CONF_NAME", "name"),
            patch("custom_components.adaptive_climate.climate_setup.discovery") as mock_discovery,
            patch("custom_components.adaptive_climate.climate_setup.entity_platform") as mock_ep,
        ):
            mock_ep.current_platform.get.return_value = MagicMock()
            await async_setup_platform(hass, config, MagicMock())

        # Verify 'number' platform was discovered
        number_calls = [c for c in mock_discovery.async_load_platform.call_args_list if c[0][1] == "number"]
        assert len(number_calls) == 1, (
            f"Expected exactly 1 call to async_load_platform('number'), got {len(number_calls)}. "
            "M02: climate_setup must trigger number platform discovery for LearningWindowNumber."
        )

    @pytest.mark.asyncio
    async def test_number_platform_not_loaded_twice(self):
        """M02 regression: number platform must only be discovered once (guard flag)."""
        from unittest.mock import AsyncMock, MagicMock, patch
        from custom_components.adaptive_climate.climate_setup import async_setup_platform
        from custom_components.adaptive_climate.const import DOMAIN

        mock_existing_store = AsyncMock()

        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "learning_store": mock_existing_store,
                "number_platform_loaded": True,  # already loaded on first zone
            }
        }
        hass.config.units.temperature_unit = "°C"

        config = {"name": "Test Zone 2"}  # No heater → early return

        with (
            patch("custom_components.adaptive_climate.climate_setup.CONF_NAME", "name"),
            patch("custom_components.adaptive_climate.climate_setup.discovery") as mock_discovery,
            patch("custom_components.adaptive_climate.climate_setup.entity_platform") as mock_ep,
        ):
            mock_ep.current_platform.get.return_value = MagicMock()
            await async_setup_platform(hass, config, MagicMock())

        number_calls = [c for c in mock_discovery.async_load_platform.call_args_list if c[0][1] == "number"]
        assert len(number_calls) == 0, (
            "number platform must not be loaded again when number_platform_loaded flag is set."
        )
