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
    CONF_WATER_TEMP_EXTRA_SENSORS,
    CONF_WATER_TEMP_FALLBACK_HUMIDITY,
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
    DEFAULT_WATER_TEMP_FALLBACK_HUMIDITY,
    DEFAULT_WATER_TEMP_HEATING_RAMP_RATE,
    DEFAULT_WATER_TEMP_HEATING_RAMP_START,
    DEFAULT_WATER_TEMP_IDLE_DAYS,
    DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP,
    DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL,
    DOMAIN,
    WATER_TEMP_HEATING_TARGET_MAX,
    WATER_TEMP_HEATING_TARGET_MIN,
    WATER_TEMP_MODE_COOLING,
    WATER_TEMP_MODE_HEATING,
)


def _cooling(
    entity: str = "number.hp_cool",
    *,
    min_supply_temp: float | None = None,
    ramp_start: float | None = None,
) -> dict:
    block = {CONF_WATER_TEMP_TARGET_ENTITY: entity}
    if min_supply_temp is not None:
        block[CONF_WATER_TEMP_MIN_SUPPLY_TEMP] = min_supply_temp
    if ramp_start is not None:
        block[CONF_WATER_TEMP_RAMP_START] = ramp_start
    return block


def _heating(
    entity: str = "number.hp_heat",
    target: float | None = 35.0,
    *,
    ramp_start: float | None = None,
) -> dict:
    block = {CONF_WATER_TEMP_TARGET_ENTITY: entity}
    if target is not None:
        block[CONF_WATER_TEMP_TARGET] = target
    if ramp_start is not None:
        block[CONF_WATER_TEMP_RAMP_START] = ramp_start
    return block


# --- constants -------------------------------------------------------------


def test_spec_defaults_are_the_user_approved_values():
    """Reviewer-kept defaults must not drift."""
    assert DEFAULT_WATER_TEMP_IDLE_DAYS == 7
    assert DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL == 1800
    assert DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP == 18.0
    assert DEFAULT_WATER_TEMP_DEW_POINT_MARGIN == 2.0
    assert DEFAULT_WATER_TEMP_FALLBACK_HUMIDITY == 65
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


# --- cross-key validator: ramp_start vs. safety floor / target -------------


def test_validator_rejects_cooling_ramp_start_below_min_supply_temp():
    """A ramp_start below the safety floor would have parks/interlocks write
    below min_supply_temp — the whole point of the floor."""
    config = {
        CONF_WATER_TEMP_CONTROL: {
            CONF_WATER_TEMP_COOLING: _cooling(min_supply_temp=20.0, ramp_start=19.9),
        }
    }
    with pytest.raises(vol.Invalid, match=r"cooling.ramp_start"):
        validate_water_temp_control(config)


def test_validator_accepts_cooling_ramp_start_equal_to_min_supply_temp():
    """Equal-value boundary is accepted (>=, not strictly >)."""
    config = {
        CONF_WATER_TEMP_CONTROL: {
            CONF_WATER_TEMP_COOLING: _cooling(min_supply_temp=20.0, ramp_start=20.0),
        }
    }
    assert validate_water_temp_control(config) is config


def test_validator_rejects_cooling_ramp_start_below_default_min_supply_temp():
    """Rule must apply even when min_supply_temp relies on its schema default
    (validator runs on raw dicts that may not have defaults applied yet)."""
    config = {
        CONF_WATER_TEMP_CONTROL: {
            CONF_WATER_TEMP_COOLING: _cooling(ramp_start=DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP - 0.1),
        }
    }
    with pytest.raises(vol.Invalid, match=r"cooling.ramp_start"):
        validate_water_temp_control(config)


def test_validator_rejects_heating_ramp_start_above_explicit_target():
    """A ramp_start above the target would immediately clamp up — the ramp
    never actually ramps."""
    config = {
        CONF_WATER_TEMP_CONTROL: {
            CONF_WATER_TEMP_HEATING: _heating(target=30.0, ramp_start=30.1),
        }
    }
    with pytest.raises(vol.Invalid, match=r"heating.ramp_start"):
        validate_water_temp_control(config)


def test_validator_accepts_heating_ramp_start_equal_to_target():
    """Equal-value boundary is accepted (<=, not strictly <)."""
    config = {
        CONF_WATER_TEMP_CONTROL: {
            CONF_WATER_TEMP_HEATING: _heating(target=30.0, ramp_start=30.0),
        }
    }
    assert validate_water_temp_control(config) is config


def test_validator_rejects_heating_ramp_start_above_supply_temperature_fallback():
    """Rule must also cover the supply_temperature fallback path, not just an
    explicit heating.target."""
    config = {
        CONF_SUPPLY_TEMPERATURE: 30.0,
        CONF_WATER_TEMP_CONTROL: {
            CONF_WATER_TEMP_HEATING: _heating(target=None, ramp_start=30.1),
        },
    }
    with pytest.raises(vol.Invalid, match=r"heating.ramp_start"):
        validate_water_temp_control(config)


def test_validator_accepts_heating_ramp_start_equal_to_supply_temperature_fallback():
    config = {
        CONF_SUPPLY_TEMPERATURE: 30.0,
        CONF_WATER_TEMP_CONTROL: {
            CONF_WATER_TEMP_HEATING: _heating(target=None, ramp_start=30.0),
        },
    }
    assert validate_water_temp_control(config) is config


def test_validator_rejects_heating_ramp_start_above_default_target():
    """Rule must apply even when ramp_start relies on its schema default
    (validator runs on raw dicts that may not have defaults applied yet)."""
    config = {
        CONF_WATER_TEMP_CONTROL: {
            CONF_WATER_TEMP_HEATING: _heating(target=DEFAULT_WATER_TEMP_HEATING_RAMP_START - 0.1),
        }
    }
    with pytest.raises(vol.Invalid, match=r"heating.ramp_start"):
        validate_water_temp_control(config)


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
    assert cooling[CONF_WATER_TEMP_FALLBACK_HUMIDITY] == DEFAULT_WATER_TEMP_FALLBACK_HUMIDITY
    assert cooling[CONF_WATER_TEMP_RAMP_START] == DEFAULT_WATER_TEMP_COOLING_RAMP_START
    assert cooling[CONF_WATER_TEMP_RAMP_RATE] == DEFAULT_WATER_TEMP_COOLING_RAMP_RATE
    assert cooling[CONF_WATER_TEMP_EXTRA_SENSORS] == []
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


def test_extra_sensors_accepts_a_single_mapping_not_wrapped_in_a_list():
    """YAML shorthand: one pair need not be wrapped in a list."""
    from custom_components.adaptive_climate import WATER_TEMP_CONTROL_SCHEMA

    if WATER_TEMP_CONTROL_SCHEMA is None:
        pytest.skip("Home Assistant not installed; schema is stubbed to None")

    result = WATER_TEMP_CONTROL_SCHEMA(
        {
            CONF_WATER_TEMP_COOLING: {
                CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_cool",
                CONF_WATER_TEMP_EXTRA_SENSORS: {
                    "humidity": "sensor.manifold_rh",
                    "temperature": "sensor.manifold_temp",
                },
            }
        }
    )
    pair = result[CONF_WATER_TEMP_COOLING][CONF_WATER_TEMP_EXTRA_SENSORS][0]
    assert pair["humidity"] == "sensor.manifold_rh"
    assert pair["temperature"] == "sensor.manifold_temp"


# --- heating target range boundaries ---------------------------------------


def test_heating_target_bounds_constants_are_20_to_45():
    assert WATER_TEMP_HEATING_TARGET_MIN == 20.0
    assert WATER_TEMP_HEATING_TARGET_MAX == 45.0


def test_schema_accepts_heating_target_at_range_boundaries():
    from custom_components.adaptive_climate import WATER_TEMP_CONTROL_SCHEMA

    if WATER_TEMP_CONTROL_SCHEMA is None:
        pytest.skip("Home Assistant not installed; schema is stubbed to None")

    for boundary in (WATER_TEMP_HEATING_TARGET_MIN, WATER_TEMP_HEATING_TARGET_MAX):
        result = WATER_TEMP_CONTROL_SCHEMA(
            {
                CONF_WATER_TEMP_HEATING: {
                    CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_heat",
                    CONF_WATER_TEMP_TARGET: boundary,
                }
            }
        )
        assert result[CONF_WATER_TEMP_HEATING][CONF_WATER_TEMP_TARGET] == boundary


def test_schema_rejects_heating_target_just_outside_range_boundaries():
    from custom_components.adaptive_climate import WATER_TEMP_CONTROL_SCHEMA

    if WATER_TEMP_CONTROL_SCHEMA is None:
        pytest.skip("Home Assistant not installed; schema is stubbed to None")

    for boundary in (WATER_TEMP_HEATING_TARGET_MIN - 0.1, WATER_TEMP_HEATING_TARGET_MAX + 0.1):
        with pytest.raises(vol.Invalid):
            WATER_TEMP_CONTROL_SCHEMA(
                {
                    CONF_WATER_TEMP_HEATING: {
                        CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_heat",
                        CONF_WATER_TEMP_TARGET: boundary,
                    }
                }
            )


# --- _water_temp_entity_id ---------------------------------------------------


def test_entity_id_validator_lowercases_the_value():
    """Case must be normalized so distinctness checks can't be bypassed by case."""
    from custom_components.adaptive_climate import _water_temp_entity_id

    assert _water_temp_entity_id("number.HP") == "number.hp"
    assert _water_temp_entity_id("Number.Hp_Cool") == "number.hp_cool"


def test_entity_id_validator_rejects_non_string():
    from custom_components.adaptive_climate import _water_temp_entity_id

    with pytest.raises(vol.Invalid):
        _water_temp_entity_id(123)


@pytest.mark.parametrize(
    "bad_entity_id",
    [
        "not_an_entity_id",
        "number.",
        ".hp",
        "num ber.hp",
        "number..hp",
        "_number.hp",
        "number._hp",
        "number.hp_",
        "number.hp__x",
        "",
    ],
)
def test_entity_id_validator_rejects_malformed_ids(bad_entity_id):
    from custom_components.adaptive_climate import _water_temp_entity_id

    with pytest.raises(vol.Invalid):
        _water_temp_entity_id(bad_entity_id)


# --- _water_temp_ensure_list -------------------------------------------------


def test_ensure_list_wraps_a_single_mapping():
    from custom_components.adaptive_climate import _water_temp_ensure_list

    pair = {"humidity": "sensor.manifold_rh", "temperature": "sensor.manifold_temp"}
    assert _water_temp_ensure_list(pair) == [pair]


def test_ensure_list_passes_through_a_list():
    from custom_components.adaptive_climate import _water_temp_ensure_list

    assert _water_temp_ensure_list([1, 2]) == [1, 2]


def test_ensure_list_treats_none_as_empty():
    from custom_components.adaptive_climate import _water_temp_ensure_list

    assert _water_temp_ensure_list(None) == []


# --- E2E: CONFIG_SCHEMA wiring ----------------------------------------------


def test_config_schema_wiring_catches_case_variant_duplicate_target_entities():
    """E2E: CONFIG_SCHEMA must run WATER_TEMP_CONTROL_SCHEMA (which lowercases
    entity IDs) before validate_water_temp_control's distinctness check fires,
    so a case-variant duplicate (number.HP vs number.hp) is still caught by
    the full vol.All(vol.Schema(...), validate_water_temp_control) wiring —
    not just by calling either piece in isolation.
    """
    from custom_components.adaptive_climate import CONFIG_SCHEMA

    if CONFIG_SCHEMA is None:
        pytest.skip("Home Assistant not installed; schema is stubbed to None")

    config = {
        DOMAIN: {
            CONF_WATER_TEMP_CONTROL: {
                CONF_WATER_TEMP_COOLING: {CONF_WATER_TEMP_TARGET_ENTITY: "number.HP"},
                CONF_WATER_TEMP_HEATING: {
                    CONF_WATER_TEMP_TARGET_ENTITY: "number.hp",
                    CONF_WATER_TEMP_TARGET: 35.0,
                },
            }
        }
    }

    with pytest.raises(vol.Invalid, match="must differ"):
        CONFIG_SCHEMA(config)


def test_config_schema_wiring_catches_cooling_ramp_start_below_min_supply_temp():
    """E2E: both fields individually pass WATER_TEMP_CONTROL_SCHEMA's per-field
    ranges, so only the cross-key validate_water_temp_control() step catches
    the unsafe combination through the full CONFIG_SCHEMA wiring."""
    from custom_components.adaptive_climate import CONFIG_SCHEMA

    if CONFIG_SCHEMA is None:
        pytest.skip("Home Assistant not installed; schema is stubbed to None")

    config = {
        DOMAIN: {
            CONF_WATER_TEMP_CONTROL: {
                CONF_WATER_TEMP_COOLING: {
                    CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_cool",
                    CONF_WATER_TEMP_MIN_SUPPLY_TEMP: 25.0,
                    CONF_WATER_TEMP_RAMP_START: 20.0,
                },
            }
        }
    }

    with pytest.raises(vol.Invalid, match=r"cooling.ramp_start"):
        CONFIG_SCHEMA(config)


def test_config_schema_wiring_catches_heating_ramp_start_above_target():
    """E2E: both fields individually pass WATER_TEMP_CONTROL_SCHEMA's per-field
    ranges, so only the cross-key validate_water_temp_control() step catches
    the unsafe combination through the full CONFIG_SCHEMA wiring."""
    from custom_components.adaptive_climate import CONFIG_SCHEMA

    if CONFIG_SCHEMA is None:
        pytest.skip("Home Assistant not installed; schema is stubbed to None")

    config = {
        DOMAIN: {
            CONF_WATER_TEMP_CONTROL: {
                CONF_WATER_TEMP_HEATING: {
                    CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_heat",
                    CONF_WATER_TEMP_TARGET: 30.0,
                    CONF_WATER_TEMP_RAMP_START: 35.0,
                },
            }
        }
    }

    with pytest.raises(vol.Invalid, match=r"heating.ramp_start"):
        CONFIG_SCHEMA(config)
