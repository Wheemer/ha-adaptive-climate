"""Tests for water_temp_control constants, schema and cross-key validation."""

from __future__ import annotations

import pytest
import voluptuous as vol

from custom_components.adaptive_climate import validate_water_temp_control
from custom_components.adaptive_climate.const import (
    CONF_EXCLUDE_FROM_DEW_POINT,
    CONF_SUPPLY_TEMPERATURE,
    CONF_WATER_TEMP_CONTROL,
    CONF_WATER_TEMP_COOLING,
    CONF_WATER_TEMP_DEW_POINT_MARGIN,
    CONF_WATER_TEMP_HEATING,
    CONF_WATER_TEMP_IDLE_DAYS,
    CONF_WATER_TEMP_MIN_SUPPLY_TEMP,
    CONF_WATER_TEMP_MIN_WRITE_INTERVAL,
    CONF_WATER_TEMP_RAMP_RATE,
    CONF_WATER_TEMP_RAMP_START,
    CONF_WATER_TEMP_TARGET,
    CONF_WATER_TEMP_TARGET_ENTITY,
    DEFAULT_WATER_TEMP_COOLING_RAMP_RATE,
    DEFAULT_WATER_TEMP_COOLING_RAMP_START,
    DEFAULT_WATER_TEMP_DEW_POINT_MARGIN,
    DEFAULT_WATER_TEMP_HEATING_RAMP_RATE,
    DEFAULT_WATER_TEMP_HEATING_RAMP_START,
    DEFAULT_WATER_TEMP_IDLE_DAYS,
    DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP,
    DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL,
    WATER_TEMP_MODE_COOLING,
    WATER_TEMP_MODE_HEATING,
)


def _cooling(entity: str = "number.hp_cool") -> dict:
    return {CONF_WATER_TEMP_TARGET_ENTITY: entity}


def _heating(entity: str = "number.hp_heat", target: float | None = 35.0) -> dict:
    block = {CONF_WATER_TEMP_TARGET_ENTITY: entity}
    if target is not None:
        block[CONF_WATER_TEMP_TARGET] = target
    return block


# --- constants -------------------------------------------------------------


def test_spec_defaults_are_the_user_approved_values():
    """Reviewer-kept defaults must not drift."""
    assert DEFAULT_WATER_TEMP_IDLE_DAYS == 7
    assert DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL == 1800
    assert DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP == 18.0
    assert DEFAULT_WATER_TEMP_DEW_POINT_MARGIN == 2.0
    assert DEFAULT_WATER_TEMP_COOLING_RAMP_START == 22.0
    assert DEFAULT_WATER_TEMP_COOLING_RAMP_RATE == 1.0
    assert DEFAULT_WATER_TEMP_HEATING_RAMP_START == 25.0
    assert DEFAULT_WATER_TEMP_HEATING_RAMP_RATE == 2.0


def test_config_key_names_match_the_yaml_surface():
    """Key strings are the public YAML surface — pin them."""
    assert CONF_WATER_TEMP_CONTROL == "water_temp_control"
    assert CONF_WATER_TEMP_COOLING == "cooling"
    assert CONF_WATER_TEMP_HEATING == "heating"
    assert CONF_WATER_TEMP_TARGET_ENTITY == "target_entity"
    assert CONF_WATER_TEMP_MIN_SUPPLY_TEMP == "min_supply_temp"
    assert CONF_WATER_TEMP_DEW_POINT_MARGIN == "dew_point_margin"
    assert CONF_WATER_TEMP_RAMP_START == "ramp_start"
    assert CONF_WATER_TEMP_RAMP_RATE == "ramp_rate"
    assert CONF_WATER_TEMP_IDLE_DAYS == "idle_days"
    assert CONF_WATER_TEMP_MIN_WRITE_INTERVAL == "min_write_interval"
    assert CONF_EXCLUDE_FROM_DEW_POINT == "exclude_from_dew_point"
    assert WATER_TEMP_MODE_COOLING == "cooling"
    assert WATER_TEMP_MODE_HEATING == "heating"


def test_margin_key_does_not_collide_with_cooling_supply_margin():
    """The new key must be distinct from the pre-existing, differently-scoped one."""
    from custom_components.adaptive_climate.const import CONF_COOLING_SUPPLY_MARGIN

    assert CONF_WATER_TEMP_DEW_POINT_MARGIN != CONF_COOLING_SUPPLY_MARGIN


# --- cross-key validator ---------------------------------------------------


def test_validator_passes_through_config_without_water_temp_block():
    config = {"sync_modes": True}
    assert validate_water_temp_control(config) is config


def test_validator_accepts_cooling_only():
    config = {CONF_WATER_TEMP_CONTROL: {CONF_WATER_TEMP_COOLING: _cooling()}}
    assert validate_water_temp_control(config) is config


def test_validator_accepts_heating_with_explicit_target():
    config = {CONF_WATER_TEMP_CONTROL: {CONF_WATER_TEMP_HEATING: _heating(target=35.0)}}
    assert validate_water_temp_control(config) is config


def test_validator_accepts_heating_target_falling_back_to_supply_temperature():
    config = {
        CONF_SUPPLY_TEMPERATURE: 40.0,
        CONF_WATER_TEMP_CONTROL: {CONF_WATER_TEMP_HEATING: _heating(target=None)},
    }
    assert validate_water_temp_control(config) is config


def test_validator_rejects_heating_with_no_target_anywhere():
    config = {CONF_WATER_TEMP_CONTROL: {CONF_WATER_TEMP_HEATING: _heating(target=None)}}
    with pytest.raises(vol.Invalid, match="supply_temperature"):
        validate_water_temp_control(config)


def test_validator_rejects_supply_temperature_fallback_outside_heating_range():
    """supply_temperature is validated to 25-80; the heating target range is 20-45."""
    config = {
        CONF_SUPPLY_TEMPERATURE: 70.0,
        CONF_WATER_TEMP_CONTROL: {CONF_WATER_TEMP_HEATING: _heating(target=None)},
    }
    with pytest.raises(vol.Invalid, match="outside the water_temp_control heating"):
        validate_water_temp_control(config)


def test_validator_rejects_identical_target_entities():
    config = {
        CONF_WATER_TEMP_CONTROL: {
            CONF_WATER_TEMP_COOLING: _cooling("number.hp_supply"),
            CONF_WATER_TEMP_HEATING: _heating("number.hp_supply", target=35.0),
        }
    }
    with pytest.raises(vol.Invalid, match="must differ"):
        validate_water_temp_control(config)


def test_validator_accepts_distinct_target_entities():
    config = {
        CONF_WATER_TEMP_CONTROL: {
            CONF_WATER_TEMP_COOLING: _cooling("number.hp_cool"),
            CONF_WATER_TEMP_HEATING: _heating("number.hp_heat", target=35.0),
        }
    }
    assert validate_water_temp_control(config) is config


# --- voluptuous schema -----------------------------------------------------


def test_schema_applies_all_defaults():
    from custom_components.adaptive_climate import WATER_TEMP_CONTROL_SCHEMA

    if WATER_TEMP_CONTROL_SCHEMA is None:
        pytest.skip("Home Assistant not installed; schema is stubbed to None")

    result = WATER_TEMP_CONTROL_SCHEMA(
        {
            CONF_WATER_TEMP_COOLING: {CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_cool"},
            CONF_WATER_TEMP_HEATING: {
                CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_heat",
                CONF_WATER_TEMP_TARGET: 35.0,
            },
        }
    )

    assert result[CONF_WATER_TEMP_IDLE_DAYS] == DEFAULT_WATER_TEMP_IDLE_DAYS
    assert result[CONF_WATER_TEMP_MIN_WRITE_INTERVAL] == DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL
    cooling = result[CONF_WATER_TEMP_COOLING]
    assert cooling[CONF_WATER_TEMP_MIN_SUPPLY_TEMP] == DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP
    assert cooling[CONF_WATER_TEMP_DEW_POINT_MARGIN] == DEFAULT_WATER_TEMP_DEW_POINT_MARGIN
    assert cooling[CONF_WATER_TEMP_RAMP_START] == DEFAULT_WATER_TEMP_COOLING_RAMP_START
    assert cooling[CONF_WATER_TEMP_RAMP_RATE] == DEFAULT_WATER_TEMP_COOLING_RAMP_RATE
    assert cooling["extra_sensors"] == []
    heating = result[CONF_WATER_TEMP_HEATING]
    assert heating[CONF_WATER_TEMP_RAMP_START] == DEFAULT_WATER_TEMP_HEATING_RAMP_START
    assert heating[CONF_WATER_TEMP_RAMP_RATE] == DEFAULT_WATER_TEMP_HEATING_RAMP_RATE


def test_schema_requires_cooling_target_entity():
    from custom_components.adaptive_climate import WATER_TEMP_CONTROL_SCHEMA

    if WATER_TEMP_CONTROL_SCHEMA is None:
        pytest.skip("Home Assistant not installed; schema is stubbed to None")

    with pytest.raises(vol.Invalid):
        WATER_TEMP_CONTROL_SCHEMA({CONF_WATER_TEMP_COOLING: {}})


def test_schema_rejects_heating_target_out_of_range():
    from custom_components.adaptive_climate import WATER_TEMP_CONTROL_SCHEMA

    if WATER_TEMP_CONTROL_SCHEMA is None:
        pytest.skip("Home Assistant not installed; schema is stubbed to None")

    with pytest.raises(vol.Invalid):
        WATER_TEMP_CONTROL_SCHEMA(
            {
                CONF_WATER_TEMP_HEATING: {
                    CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_heat",
                    CONF_WATER_TEMP_TARGET: 60.0,
                }
            }
        )


def test_schema_parses_extra_sensor_pairs():
    from custom_components.adaptive_climate import WATER_TEMP_CONTROL_SCHEMA

    if WATER_TEMP_CONTROL_SCHEMA is None:
        pytest.skip("Home Assistant not installed; schema is stubbed to None")

    result = WATER_TEMP_CONTROL_SCHEMA(
        {
            CONF_WATER_TEMP_COOLING: {
                CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_cool",
                "extra_sensors": [{"humidity": "sensor.manifold_rh", "temperature": "sensor.manifold_temp"}],
            }
        }
    )
    pair = result[CONF_WATER_TEMP_COOLING]["extra_sensors"][0]
    assert pair["humidity"] == "sensor.manifold_rh"
    assert pair["temperature"] == "sensor.manifold_temp"
