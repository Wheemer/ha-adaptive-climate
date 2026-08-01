"""Tests for WaterTempController: targets, ramps, writes, interlocks, gate."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.adaptive_climate.const import (
    WATER_TEMP_BINDING_BLIND,
    WATER_TEMP_BINDING_DEW_POINT,
    WATER_TEMP_BINDING_MIN_SUPPLY,
    WATER_TEMP_BINDING_RAMP,
    WATER_TEMP_BINDING_TARGET,
    WATER_TEMP_MODE_COOLING,
    WATER_TEMP_MODE_HEATING,
)
from custom_components.adaptive_climate.managers.water_temp_controller import (
    WaterTempController,
)
from custom_components.adaptive_climate.managers.water_temp_sources import DewPointScan

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

COOL_ENTITY = "number.hp_cool_supply"
HEAT_ENTITY = "number.hp_heat_supply"


def cooling_config(**overrides):
    config = {
        "target_entity": COOL_ENTITY,
        "min_supply_temp": 18.0,
        "dew_point_margin": 2.0,
        "fallback_humidity": 65.0,
        "ramp_start": 22.0,
        "ramp_rate": 1.0,
        "extra_sensors": [],
    }
    config.update(overrides)
    return config


def heating_config(**overrides):
    config = {
        "target_entity": HEAT_ENTITY,
        "target": 35.0,
        "ramp_start": 25.0,
        "ramp_rate": 2.0,
    }
    config.update(overrides)
    return config


def number_state(value, *, step=0.5, minimum=15.0, maximum=45.0):
    state = MagicMock()
    state.state = str(value)
    state.attributes = {"step": step, "min": minimum, "max": maximum}
    return state


def climate_state(mode, overrides=None):
    state = MagicMock()
    state.state = mode
    state.attributes = {"status": {"overrides": overrides or []}}
    return state


def build_controller(*, cooling=None, heating=None, zones_in_mode=None, states=None, **top_level):
    """Construct a controller with the scanner stubbed out."""
    hass = MagicMock()
    hass.states.get = (states or {}).get
    hass.services.async_call = AsyncMock(return_value=None)

    coordinator = MagicMock()
    zones_in_mode = zones_in_mode or {}
    coordinator.get_zones_in_mode = lambda mode: zones_in_mode.get(mode, {})

    config = {"idle_days": 7, "min_write_interval": 1800}
    config.update(top_level)
    if cooling is not None:
        config["cooling"] = cooling
    if heating is not None:
        config["heating"] = heating

    controller = WaterTempController(hass, coordinator, config)
    controller.mark_restored()
    return controller


def stub_scan(controller, dew_point=None, *, blind=False, worst_source="living"):
    controller._scanner = MagicMock()
    controller._scanner.scan = MagicMock(
        return_value=DewPointScan(
            dew_point=dew_point,
            worst_source=worst_source,
            blind=blind,
            readings=(),
        )
    )


# =============================================================================
# Targets
# =============================================================================


class TestCoolingTarget:
    def test_dew_point_plus_margin(self):
        # Spec (2026-08-01-water-temp-control-design.md:84): "first run -> ramp,
        # conservative in both directions". A fresh controller always starts a
        # cooling ramp at ramp_start=22.0, and effective = max(dew_target, ramp)
        # while ramping — so target-only assertions must first move past the
        # ramp window, matching every other target/write test in this file.
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(20.0)},
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        targets = controller.compute_targets(NOW)

        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(19.0)
        assert controller.binding[WATER_TEMP_MODE_COOLING] == WATER_TEMP_BINDING_DEW_POINT

    def test_min_supply_temp_floors_the_target(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(20.0)},
        )
        stub_scan(controller, dew_point=10.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        targets = controller.compute_targets(NOW)

        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(18.0)
        assert controller.binding[WATER_TEMP_MODE_COOLING] == WATER_TEMP_BINDING_MIN_SUPPLY

    def test_blind_mode_floors_at_twenty(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(20.0)},
        )
        stub_scan(controller, dew_point=14.0, blind=True)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        targets = controller.compute_targets(NOW)

        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(20.0)
        assert controller.binding[WATER_TEMP_MODE_COOLING] == WATER_TEMP_BINDING_BLIND

    def test_blind_mode_respects_a_higher_min_supply_temp(self):
        controller = build_controller(
            cooling=cooling_config(min_supply_temp=24.0),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(26.0)},
        )
        stub_scan(controller, dew_point=None, blind=True)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        targets = controller.compute_targets(NOW)

        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(24.0)

    def test_no_cool_zones_means_no_cooling_target(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=17.0)

        assert WATER_TEMP_MODE_COOLING not in controller.compute_targets(NOW)


class TestHeatingTarget:
    def test_configured_target_is_used(self):
        controller = build_controller(
            heating=heating_config(),
            zones_in_mode={"heat": {"living": {}}},
            states={HEAT_ENTITY: number_state(35.0)},
        )
        controller._ramp[WATER_TEMP_MODE_HEATING].last_active = NOW - timedelta(hours=1)

        targets = controller.compute_targets(NOW)

        assert targets[WATER_TEMP_MODE_HEATING] == pytest.approx(35.0)
        assert controller.binding[WATER_TEMP_MODE_HEATING] == WATER_TEMP_BINDING_TARGET

    def test_target_falls_back_to_supply_temperature(self):
        hass = MagicMock()
        hass.states.get = {HEAT_ENTITY: number_state(40.0)}.get
        hass.services.async_call = AsyncMock(return_value=None)
        coordinator = MagicMock()
        coordinator.get_zones_in_mode = lambda mode: {"living": {}} if mode == "heat" else {}

        controller = WaterTempController(
            hass,
            coordinator,
            {"heating": {k: v for k, v in heating_config().items() if k != "target"}},
            supply_temperature=40.0,
        )
        controller.mark_restored()
        controller._ramp[WATER_TEMP_MODE_HEATING].last_active = NOW - timedelta(hours=1)

        assert controller.compute_targets(NOW)[WATER_TEMP_MODE_HEATING] == pytest.approx(40.0)

    def test_no_heat_zones_means_no_heating_target(self):
        controller = build_controller(
            heating=heating_config(),
            zones_in_mode={"heat": {}},
            states={HEAT_ENTITY: number_state(35.0)},
        )
        assert WATER_TEMP_MODE_HEATING not in controller.compute_targets(NOW)


# =============================================================================
# Ramps
# =============================================================================


class TestRamps:
    def test_first_run_starts_a_ramp(self):
        """No persisted state is treated as long-idle: conservative both ways."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0)

        targets = controller.compute_targets(NOW)

        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(22.0)
        assert controller.binding[WATER_TEMP_MODE_COOLING] == WATER_TEMP_BINDING_RAMP
        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started == NOW

    def test_cooling_ramp_descends_at_the_configured_rate(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0)
        controller.compute_targets(NOW)

        assert controller.compute_targets(NOW + timedelta(days=2))[WATER_TEMP_MODE_COOLING] == pytest.approx(20.0)

    def test_cooling_ramp_ends_when_it_reaches_the_dew_target(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0)
        controller.compute_targets(NOW)

        later = controller.compute_targets(NOW + timedelta(days=10))

        assert later[WATER_TEMP_MODE_COOLING] == pytest.approx(18.0)
        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started is None

    def test_heating_ramp_ascends_and_ends_at_target(self):
        controller = build_controller(
            heating=heating_config(),
            zones_in_mode={"heat": {"living": {}}},
            states={HEAT_ENTITY: number_state(25.0)},
        )
        controller.compute_targets(NOW)

        assert controller.compute_targets(NOW + timedelta(days=2))[WATER_TEMP_MODE_HEATING] == pytest.approx(29.0)
        assert controller.compute_targets(NOW + timedelta(days=10))[WATER_TEMP_MODE_HEATING] == pytest.approx(35.0)
        assert controller.ramp_state[WATER_TEMP_MODE_HEATING].ramp_started is None

    def test_heating_ramp_seeds_from_the_entity_when_it_runs_hotter(self):
        """A system already at 33 degC must not be yanked down to 25 (backup heater trap)."""
        controller = build_controller(
            heating=heating_config(),
            zones_in_mode={"heat": {"living": {}}},
            states={HEAT_ENTITY: number_state(33.0)},
        )

        assert controller.compute_targets(NOW)[WATER_TEMP_MODE_HEATING] == pytest.approx(33.0)
        assert controller.ramp_state[WATER_TEMP_MODE_HEATING].ramp_start_value == pytest.approx(33.0)

    def test_cooling_ramp_never_seeds_from_the_entity(self):
        """Seeding cooling from a cold entity would start too cold on a warm slab."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(16.0)},
        )
        stub_scan(controller, dew_point=14.0)

        assert controller.compute_targets(NOW)[WATER_TEMP_MODE_COOLING] == pytest.approx(22.0)

    def test_idle_shorter_than_idle_days_does_not_restart_a_ramp(self):
        """Shoulder-season HEAT/COOL flips must not restart the ramp."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(18.0)},
        )
        stub_scan(controller, dew_point=14.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(days=3)

        targets = controller.compute_targets(NOW)

        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started is None
        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(18.0)

    def test_idle_beyond_idle_days_restarts_the_ramp(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(18.0)},
        )
        stub_scan(controller, dew_point=14.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(days=30)

        targets = controller.compute_targets(NOW)

        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started == NOW
        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(22.0)

    def test_in_progress_ramp_continues_from_its_own_start_time(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0)
        controller.compute_targets(NOW)
        started = controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started

        controller.compute_targets(NOW + timedelta(days=1))

        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started == started

    def test_heating_and_cooling_ramps_are_independent(self):
        controller = build_controller(
            cooling=cooling_config(),
            heating=heating_config(),
            zones_in_mode={"cool": {"living": {}}, "heat": {}},
            states={COOL_ENTITY: number_state(22.0), HEAT_ENTITY: number_state(35.0)},
        )
        stub_scan(controller, dew_point=14.0)

        controller.compute_targets(NOW)

        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started == NOW
        assert controller.ramp_state[WATER_TEMP_MODE_HEATING].ramp_started is None


# =============================================================================
# Persistence round-trip
# =============================================================================


class TestPersistenceState:
    def test_state_round_trips_through_iso_strings(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0)
        controller.compute_targets(NOW)

        state = controller.get_state_for_persistence()
        assert state[WATER_TEMP_MODE_COOLING]["ramp_started"] == NOW.isoformat()

        restored = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        restored.restore_state(state)

        assert restored.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started == NOW

    def test_future_ramp_start_is_clamped_to_now_on_restore(self):
        """Clock corrections must never yield a negative elapsed time."""
        controller = build_controller(cooling=cooling_config())
        future = (NOW + timedelta(days=400)).isoformat()

        controller.restore_state({WATER_TEMP_MODE_COOLING: {"ramp_started": future, "last_active": future}})

        ramp = controller.ramp_state[WATER_TEMP_MODE_COOLING]
        assert ramp.ramp_started is not None
        assert ramp.ramp_started <= controller._utcnow()

    def test_restore_tolerates_missing_and_malformed_entries(self):
        controller = build_controller(cooling=cooling_config())

        controller.restore_state(None)
        controller.restore_state({WATER_TEMP_MODE_COOLING: {"ramp_started": "not-a-date"}})

        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started is None
        assert controller.restored is True

    def test_compute_is_skipped_until_state_is_restored(self):
        hass = MagicMock()
        hass.states.get = {COOL_ENTITY: number_state(22.0)}.get
        coordinator = MagicMock()
        coordinator.get_zones_in_mode = lambda mode: {"living": {}} if mode == "cool" else {}

        controller = WaterTempController(hass, coordinator, {"cooling": cooling_config()})
        stub_scan(controller, dew_point=14.0)

        assert controller.compute_targets(NOW) == {}
        assert controller.restored is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
