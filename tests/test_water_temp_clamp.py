"""Tests for unifying min_cooling_target with the dynamic water temperature."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# coordinator.py subclasses homeassistant.helpers.update_coordinator.DataUpdateCoordinator.
# conftest.py mocks most homeassistant.helpers.* submodules but not this one (only
# tests/test_coordinator.py registers it, locally, for its own legacy flat-import style).
# Register it here too (same pattern as test_water_temp_wiring.py), guarded so a
# full-suite run that already primed this via another file is a no-op.
if "homeassistant.helpers.update_coordinator" not in sys.modules:

    class _MockDataUpdateCoordinator:
        """Minimal stand-in base class - just needs to be a real, subclassable type."""

        def __init__(self, hass, logger, name, update_interval):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval

    _mock_update_coordinator_module = MagicMock()
    _mock_update_coordinator_module.DataUpdateCoordinator = _MockDataUpdateCoordinator
    sys.modules["homeassistant.helpers.update_coordinator"] = _mock_update_coordinator_module

from custom_components.adaptive_climate.const import (
    CONF_COOLING_SUPPLY_MARGIN,
    CONF_COOLING_SUPPLY_TEMP,
    CONF_WATER_TEMP_CONTROL,
    CONF_WATER_TEMP_COOLING,
    CONF_WATER_TEMP_MIN_SUPPLY_TEMP,
    CONF_WATER_TEMP_TARGET_ENTITY,
)
from custom_components.adaptive_climate.coordinator import AdaptiveThermostatCoordinator


def make_coordinator(config, controller=None):
    coordinator = AdaptiveThermostatCoordinator.__new__(AdaptiveThermostatCoordinator)
    coordinator.hass = MagicMock()
    coordinator._zones = {}
    coordinator._config = config
    coordinator._water_temp_controller = controller
    return coordinator


def controller_with(effective):
    controller = MagicMock()
    controller.effective_cooling_supply_temp = effective
    return controller


class TestMinCoolingTarget:
    def test_follows_the_controller_when_it_has_computed(self):
        coordinator = make_coordinator({CONF_COOLING_SUPPLY_MARGIN: 1.5}, controller=controller_with(19.5))

        assert coordinator.effective_cooling_supply_temp == pytest.approx(19.5)
        assert coordinator.min_cooling_target == pytest.approx(21.0)

    def test_falls_back_to_the_static_value_before_the_first_computation(self):
        coordinator = make_coordinator(
            {CONF_COOLING_SUPPLY_TEMP: 18.0, CONF_COOLING_SUPPLY_MARGIN: 1.5},
            controller=controller_with(None),
        )

        assert coordinator.effective_cooling_supply_temp == pytest.approx(18.0)
        assert coordinator.min_cooling_target == pytest.approx(19.5)

    def test_is_none_when_neither_source_is_configured(self):
        coordinator = make_coordinator({}, controller=None)

        assert coordinator.effective_cooling_supply_temp is None
        assert coordinator.min_cooling_target is None

    def test_static_only_configuration_is_unchanged(self):
        coordinator = make_coordinator(
            {CONF_COOLING_SUPPLY_TEMP: 17.0, CONF_COOLING_SUPPLY_MARGIN: 2.0}, controller=None
        )

        assert coordinator.min_cooling_target == pytest.approx(19.0)

    def test_dynamic_value_tracks_the_controller_across_updates(self):
        controller = controller_with(21.0)
        coordinator = make_coordinator({CONF_COOLING_SUPPLY_MARGIN: 1.5}, controller=controller)

        assert coordinator.min_cooling_target == pytest.approx(22.5)
        controller.effective_cooling_supply_temp = 18.5
        assert coordinator.min_cooling_target == pytest.approx(20.0)


class TestSetupConflictWarning:
    def test_warns_when_static_and_dynamic_floors_disagree(self):
        from custom_components.adaptive_climate import check_cooling_supply_conflict

        message = check_cooling_supply_conflict(
            {
                CONF_COOLING_SUPPLY_TEMP: 16.0,
                CONF_WATER_TEMP_CONTROL: {
                    CONF_WATER_TEMP_COOLING: {
                        CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_cool",
                        CONF_WATER_TEMP_MIN_SUPPLY_TEMP: 18.0,
                    }
                },
            }
        )

        assert message is not None
        assert "16.0" in message and "18.0" in message

    def test_silent_when_the_values_agree(self):
        from custom_components.adaptive_climate import check_cooling_supply_conflict

        assert (
            check_cooling_supply_conflict(
                {
                    CONF_COOLING_SUPPLY_TEMP: 18.0,
                    CONF_WATER_TEMP_CONTROL: {
                        CONF_WATER_TEMP_COOLING: {
                            CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_cool",
                            CONF_WATER_TEMP_MIN_SUPPLY_TEMP: 18.0,
                        }
                    },
                }
            )
            is None
        )

    def test_silent_without_a_static_value(self):
        from custom_components.adaptive_climate import check_cooling_supply_conflict

        assert (
            check_cooling_supply_conflict(
                {
                    CONF_WATER_TEMP_CONTROL: {
                        CONF_WATER_TEMP_COOLING: {
                            CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_cool",
                            CONF_WATER_TEMP_MIN_SUPPLY_TEMP: 18.0,
                        }
                    }
                }
            )
            is None
        )

    def test_silent_without_water_temp_cooling(self):
        from custom_components.adaptive_climate import check_cooling_supply_conflict

        assert check_cooling_supply_conflict({CONF_COOLING_SUPPLY_TEMP: 18.0}) is None

    def test_reads_the_static_value_from_auto_mode_switching_too(self):
        from custom_components.adaptive_climate import check_cooling_supply_conflict

        message = check_cooling_supply_conflict(
            {
                "auto_mode_switching": {CONF_COOLING_SUPPLY_TEMP: 16.0},
                CONF_WATER_TEMP_CONTROL: {
                    CONF_WATER_TEMP_COOLING: {
                        CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_cool",
                        CONF_WATER_TEMP_MIN_SUPPLY_TEMP: 18.0,
                    }
                },
            }
        )

        assert message is not None
