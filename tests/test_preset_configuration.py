"""Regression tests for public preset configuration and service wiring."""

from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.adaptive_climate import CONFIG_SCHEMA
from custom_components.adaptive_climate.climate_setup import async_setup_platform
from custom_components.adaptive_climate.const import DOMAIN


def test_sleep_temperature_accepted_by_domain_schema():
    config = CONFIG_SCHEMA({DOMAIN: {"sleep_temp": "20.2"}})
    assert config[DOMAIN]["sleep_temp"] == 20.2


def test_invalid_sleep_temperature_rejected():
    with pytest.raises(vol.Invalid):
        CONFIG_SCHEMA({DOMAIN: {"sleep_temp": "not a temperature"}})


@pytest.mark.asyncio
async def test_sleep_passed_to_thermostat_and_public_service_registered():
    hass = MagicMock()
    store = MagicMock()
    store.get_zone_data.return_value = None
    hass.data = {DOMAIN: {"learning_store": store, "sleep_temp": 20.2, "debug": False}}
    with (
        patch("custom_components.adaptive_climate.climate.AdaptiveThermostat"),
        patch("custom_components.adaptive_climate.thermostat_config.AdaptiveThermostatConfig") as config_class,
        patch("custom_components.adaptive_climate.climate_setup.AdaptiveLearner"),
        patch("custom_components.adaptive_climate.climate_setup.discovery"),
        patch("custom_components.adaptive_climate.climate_setup.entity_platform") as ep,
    ):
        platform = ep.current_platform.get.return_value
        await async_setup_platform(hass, {"name": "Thermostat", "heater": ["input_boolean.heat"]}, MagicMock())
    assert config_class.call_args.kwargs["sleep_temp"] == 20.2
    calls = [c for c in platform.async_register_entity_service.call_args_list if c.args[0] == "set_preset_temp"]
    assert len(calls) == 1
    assert calls[0].args[2] == "async_set_preset_temp"
    schema = vol.Schema(calls[0].args[1])
    fields = {f"{name}_temp": "20.2" for name in ("away", "eco", "boost", "comfort", "home", "sleep", "activity")}
    assert schema(fields) == dict.fromkeys(fields, 20.2)
    with pytest.raises(vol.Invalid):
        schema({"sleep_temp": "invalid"})
    with pytest.raises(vol.Invalid):
        schema({"unknown_temp": 20})
