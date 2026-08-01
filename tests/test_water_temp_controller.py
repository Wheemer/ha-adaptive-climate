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
    WATER_TEMP_BLIND_MIN_SUPPLY,
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


def build_controller(*, cooling=None, heating=None, zones_in_mode=None, states=None, all_zones=None, **top_level):
    """Construct a controller with the scanner stubbed out.

    ``all_zones`` feeds ``coordinator.get_all_zones()`` (used to detect
    registered-but-unresolvable-mode zones — see TestUnresolvableModeZones).
    Defaults to the union of every mode's zones in ``zones_in_mode``, which
    reconstructs the complete registered-zone set for every test that has no
    "invisible" zone of its own.
    """
    hass = MagicMock()
    hass.states.get = (states or {}).get
    hass.services.async_call = AsyncMock(return_value=None)

    coordinator = MagicMock()
    zones_in_mode = zones_in_mode or {}
    coordinator.get_zones_in_mode = lambda mode: zones_in_mode.get(mode, {})
    if all_zones is None:
        all_zones = {}
        for mode_zones in zones_in_mode.values():
            all_zones.update(mode_zones)
    coordinator.get_all_zones = lambda: all_zones

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


# =============================================================================
# Write policy
# =============================================================================


def written_values(controller):
    """Return the list of values passed to number.set_value."""
    return [call.args[2]["value"] for call in controller.hass.services.async_call.call_args_list]


def written_domains(controller):
    return [call.args[0] for call in controller.hass.services.async_call.call_args_list]


class TestWritePolicy:
    @pytest.mark.asyncio
    async def test_writes_the_computed_value_to_the_target_entity(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(20.0)},
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        controller.hass.services.async_call.assert_awaited_once()
        domain, service, payload = controller.hass.services.async_call.await_args.args[:3]
        assert (domain, service) == ("number", "set_value")
        assert payload == {"entity_id": COOL_ENTITY, "value": 19.0}

    @pytest.mark.asyncio
    async def test_input_number_entities_use_the_input_number_domain(self):
        entity = "input_number.hp_cool_supply"
        controller = build_controller(
            cooling=cooling_config(target_entity=entity),
            zones_in_mode={"cool": {"living": {}}},
            states={entity: number_state(20.0)},
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert written_domains(controller) == ["input_number"]

    @pytest.mark.asyncio
    async def test_cooling_rounds_up_to_the_entity_step(self):
        """Nearest-rounding would silently spend safety margin."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(20.0, step=0.5)},
        )
        stub_scan(controller, dew_point=17.1)  # 19.1 -> rounds up to 19.5
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert written_values(controller) == [19.5]

    @pytest.mark.asyncio
    async def test_heating_rounds_down_to_the_entity_step(self):
        controller = build_controller(
            heating=heating_config(target=35.3),
            zones_in_mode={"heat": {"living": {}}},
            states={HEAT_ENTITY: number_state(30.0, step=0.5)},
        )
        controller._ramp[WATER_TEMP_MODE_HEATING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert written_values(controller) == [35.0]

    @pytest.mark.asyncio
    async def test_missing_step_attribute_falls_back_to_half_a_degree(self):
        state = number_state(20.0)
        state.attributes = {"min": 15.0, "max": 45.0}
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: state},
        )
        stub_scan(controller, dew_point=17.1)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert written_values(controller) == [19.5]

    @pytest.mark.asyncio
    async def test_value_is_clamped_to_the_entity_min_and_max(self):
        controller = build_controller(
            cooling=cooling_config(min_supply_temp=5.0),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(20.0, minimum=16.0, maximum=30.0)},
        )
        stub_scan(controller, dew_point=8.0)  # 10.0, below the entity min
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert written_values(controller) == [16.0]

    @pytest.mark.asyncio
    async def test_out_of_range_value_is_not_rewritten_every_cycle(self):
        """Comparing pre-clamp values would re-issue identical calls forever."""
        controller = build_controller(
            cooling=cooling_config(min_supply_temp=5.0),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(20.0, minimum=16.0, maximum=30.0)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        stub_scan(controller, dew_point=8.0)
        await controller.async_apply(NOW)
        stub_scan(controller, dew_point=7.0)  # still clamps to 16.0
        await controller.async_apply(NOW + timedelta(minutes=5))

        assert written_values(controller) == [16.0]

    @pytest.mark.asyncio
    async def test_safe_direction_change_writes_immediately(self):
        """Cooling upward is the safe direction — no dwell required."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(19.0)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        stub_scan(controller, dew_point=17.0)
        await controller.async_apply(NOW)
        stub_scan(controller, dew_point=19.0)  # 21.0, upward
        await controller.async_apply(NOW + timedelta(minutes=5))

        assert written_values(controller) == [19.0, 21.0]

    @pytest.mark.asyncio
    async def test_unsafe_direction_change_requires_the_dwell_window(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(21.0)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        stub_scan(controller, dew_point=19.0)
        await controller.async_apply(NOW)  # writes 21.0
        stub_scan(controller, dew_point=17.0)  # 19.0, downward
        await controller.async_apply(NOW + timedelta(minutes=5))
        assert written_values(controller) == [21.0]  # held

        await controller.async_apply(NOW + timedelta(minutes=40))  # > 1800 s
        assert written_values(controller) == [21.0, 19.0]

    @pytest.mark.asyncio
    async def test_dwell_timer_restarts_when_the_pending_value_changes(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(21.0)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        stub_scan(controller, dew_point=19.0)
        await controller.async_apply(NOW)
        stub_scan(controller, dew_point=17.0)
        await controller.async_apply(NOW + timedelta(minutes=20))
        stub_scan(controller, dew_point=16.0)  # different pending value, timer restarts
        await controller.async_apply(NOW + timedelta(minutes=25))
        await controller.async_apply(NOW + timedelta(minutes=40))  # only 15 min on the new value

        assert written_values(controller) == [21.0]

    @pytest.mark.asyncio
    async def test_no_dither_at_a_step_boundary_under_rh_noise(self):
        """+-1% RH noise around a rounding boundary must produce one write."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(19.5)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        for index, dew in enumerate([17.24, 17.26, 17.24, 17.26, 17.25]):
            stub_scan(controller, dew_point=dew)
            await controller.async_apply(NOW + timedelta(minutes=5 * index))

        # All five readings round up to the same 19.5: exactly one write on the
        # first cycle, then the dithering-prevention equality check (comparing
        # post-clamp values) suppresses every identical repeat.
        assert written_values(controller) == [19.5]

    @pytest.mark.asyncio
    async def test_inactive_mode_is_never_written_after_parking(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=17.0)

        await controller.async_apply(NOW)
        await controller.async_apply(NOW + timedelta(minutes=5))

        assert written_values(controller) == []

    @pytest.mark.asyncio
    async def test_deactivation_parks_the_entity_at_ramp_start(self):
        """Never leave the most aggressive value latched for the next season."""
        zones = {"cool": {"living": {}}}
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode=zones,
            states={COOL_ENTITY: number_state(19.0)},
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)
        await controller.async_apply(NOW)

        zones["cool"] = {}
        await controller.async_apply(NOW + timedelta(minutes=5))

        assert written_values(controller) == [19.0, 22.0]

    @pytest.mark.asyncio
    async def test_park_happens_exactly_once(self):
        zones = {"cool": {"living": {}}}
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode=zones,
            states={COOL_ENTITY: number_state(19.0)},
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)
        await controller.async_apply(NOW)

        zones["cool"] = {}
        await controller.async_apply(NOW + timedelta(minutes=5))
        await controller.async_apply(NOW + timedelta(minutes=10))

        assert written_values(controller) == [19.0, 22.0]

    @pytest.mark.asyncio
    async def test_service_failure_is_logged_and_retried_next_cycle(self):
        from homeassistant.exceptions import HomeAssistantError

        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(21.0)},
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)
        controller.hass.services.async_call = AsyncMock(side_effect=HomeAssistantError("boom"))

        await controller.async_apply(NOW)
        assert controller._last_written.get(COOL_ENTITY) is None

        controller.hass.services.async_call = AsyncMock(return_value=None)
        await controller.async_apply(NOW + timedelta(minutes=5))
        assert controller._last_written[COOL_ENTITY] == pytest.approx(19.0)


# =============================================================================
# Interlocks
# =============================================================================


def binary_state(value):
    state = MagicMock()
    state.state = value
    state.attributes = {}
    return state


class TestInterlocks:
    @pytest.mark.asyncio
    async def test_condensation_sensor_on_parks_immediately(self):
        """A strapped-on pipe sensor is a measurement; dew point is an inference."""
        states = {COOL_ENTITY: number_state(19.0), "binary_sensor.condensation": binary_state("on")}
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {"climate_entity_id": "climate.living"}}},
            states=states,
            condensation_sensor="binary_sensor.condensation",
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert written_values(controller) == [22.0]

    @pytest.mark.asyncio
    async def test_interlock_park_bypasses_the_dwell_window(self):
        states = {COOL_ENTITY: number_state(19.0), "binary_sensor.condensation": binary_state("off")}
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {"climate_entity_id": "climate.living"}}},
            states=states,
            condensation_sensor="binary_sensor.condensation",
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)
        await controller.async_apply(NOW)  # writes 19.0

        states["binary_sensor.condensation"] = binary_state("on")
        await controller.async_apply(NOW + timedelta(minutes=1))

        assert written_values(controller) == [19.0, 22.0]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("override_type", ["open_window", "contact_open"])
    async def test_cool_zone_window_override_forces_a_park(self, override_type):
        """Humid night air onto a cold slab is the top condensation event."""
        states = {
            COOL_ENTITY: number_state(19.0),
            "climate.living": climate_state("cool", [{"type": override_type}]),
        }
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {"climate_entity_id": "climate.living"}}},
            states=states,
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert written_values(controller) == [22.0]
        assert controller.diagnostics()["binding_constraint"] == "interlock"

    @pytest.mark.asyncio
    async def test_normal_computation_resumes_thirty_minutes_after_clear(self):
        states = {COOL_ENTITY: number_state(22.0), "binary_sensor.condensation": binary_state("on")}
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {"climate_entity_id": "climate.living"}}},
            states=states,
            condensation_sensor="binary_sensor.condensation",
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)
        await controller.async_apply(NOW)

        states["binary_sensor.condensation"] = binary_state("off")
        await controller.async_apply(NOW + timedelta(minutes=10))
        assert written_values(controller) == [22.0]  # still holding

        await controller.async_apply(NOW + timedelta(minutes=45))
        assert written_values(controller) == [22.0, 19.0]

    @pytest.mark.asyncio
    async def test_heating_is_unaffected_by_cooling_interlocks(self):
        states = {
            HEAT_ENTITY: number_state(30.0),
            COOL_ENTITY: number_state(22.0),
            "binary_sensor.condensation": binary_state("on"),
        }
        controller = build_controller(
            cooling=cooling_config(),
            heating=heating_config(),
            zones_in_mode={"cool": {}, "heat": {"living": {}}},
            states=states,
            condensation_sensor="binary_sensor.condensation",
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_HEATING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert 35.0 in written_values(controller)


# =============================================================================
# Learning gate
# =============================================================================


class TestLearningGate:
    def test_gate_is_open_while_a_ramp_is_active(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0)
        controller.compute_targets(NOW)

        assert controller.learning_gate("cool") is True
        assert controller.learning_gate(WATER_TEMP_MODE_COOLING) is True
        assert controller.learning_gate("heat") is False

    @pytest.mark.asyncio
    async def test_gate_opens_for_one_settling_window_after_a_large_write(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(21.0)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        stub_scan(controller, dew_point=17.0)
        await controller.async_apply(NOW)  # 19.0, first write, no baseline
        stub_scan(controller, dew_point=19.5)
        await controller.async_apply(NOW + timedelta(minutes=5))  # 21.5, +2.5 degC

        controller._utcnow = lambda: NOW + timedelta(minutes=30)
        assert controller.learning_gate("cool") is True

        controller._utcnow = lambda: NOW + timedelta(minutes=120)
        assert controller.learning_gate("cool") is False

    @pytest.mark.asyncio
    async def test_small_writes_do_not_open_the_gate(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(19.0)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        stub_scan(controller, dew_point=17.0)
        await controller.async_apply(NOW)  # 19.0
        stub_scan(controller, dew_point=17.4)
        await controller.async_apply(NOW + timedelta(minutes=5))  # 19.5, +0.5 degC

        controller._utcnow = lambda: NOW + timedelta(minutes=10)
        assert controller.learning_gate("cool") is False

    def test_gate_is_closed_for_unconfigured_modes_and_none(self):
        controller = build_controller(cooling=cooling_config())

        assert controller.learning_gate("heat") is False
        assert controller.learning_gate(None) is False
        assert controller.learning_gate("off") is False


# =============================================================================
# Diagnostics
# =============================================================================


class TestDiagnostics:
    def test_reports_the_active_cooling_state(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0, worst_source="kitchen")
        controller.compute_targets(NOW)

        diagnostics = controller.diagnostics()

        assert diagnostics["mode"] == WATER_TEMP_MODE_COOLING
        assert diagnostics["effective"] == pytest.approx(22.0)
        assert diagnostics["dew_point"] == pytest.approx(14.0)
        assert diagnostics["binding_constraint"] == WATER_TEMP_BINDING_RAMP
        assert diagnostics["ramp_active"] is True
        # dew_point(14.0) + margin(2.0) = 16.0, but min_supply_temp(18.0) floors
        # it — the ramp actually hands off to MIN_SUPPLY at 18.0, not 16.0, so
        # days_remaining = (22.0 ramp_start - 18.0 floor) / 1.0 ramp_rate = 4.0.
        assert diagnostics["days_remaining"] == pytest.approx(4.0)
        assert diagnostics["worst_source"] == "kitchen"

    def test_reports_nothing_when_no_mode_is_active(self):
        controller = build_controller(cooling=cooling_config(), zones_in_mode={"cool": {}})
        stub_scan(controller, dew_point=14.0)
        controller.compute_targets(NOW)

        diagnostics = controller.diagnostics()

        assert diagnostics["mode"] is None
        assert diagnostics["effective"] is None
        assert diagnostics["ramp_active"] is False


# =============================================================================
# Timers
# =============================================================================


class TestTimers:
    def test_start_registers_a_started_listener_and_an_interval(self, monkeypatch):
        controller = build_controller(cooling=cooling_config())
        tracked = {}

        def fake_interval(_hass, action, interval):
            tracked["action"] = action
            tracked["interval"] = interval
            return lambda: tracked.update(interval_cancelled=True)

        monkeypatch.setattr(
            "custom_components.adaptive_climate.managers.water_temp_controller.async_track_time_interval",
            fake_interval,
        )
        controller.hass.bus.async_listen_once = MagicMock(return_value=lambda: tracked.update(once_cancelled=True))

        controller.async_start()

        assert tracked["interval"] == timedelta(seconds=300)
        controller.hass.bus.async_listen_once.assert_called_once()

    def test_cleanup_cancels_every_registered_handle(self, monkeypatch):
        controller = build_controller(cooling=cooling_config())
        cancelled = []

        monkeypatch.setattr(
            "custom_components.adaptive_climate.managers.water_temp_controller.async_track_time_interval",
            lambda _hass, _action, _interval: lambda: cancelled.append("interval"),
        )
        controller.hass.bus.async_listen_once = MagicMock(return_value=lambda: cancelled.append("once"))

        controller.async_start()
        controller.async_cleanup()

        assert sorted(cancelled) == ["interval", "once"]

    @pytest.mark.asyncio
    async def test_a_failing_cycle_does_not_kill_the_timer(self):
        controller = build_controller(cooling=cooling_config())
        controller.async_apply = AsyncMock(side_effect=RuntimeError("boom"))

        await controller._async_timer_tick(None)  # must not raise

        controller.async_apply.assert_awaited_once()


# =============================================================================
# R4: unresolvable-mode zones (review finding #8, coordinator/controller layer)
# =============================================================================


class TestUnresolvableModeZones:
    """A registered zone whose HVAC mode can't be resolved at all (its climate
    entity has no state whatsoever) must still contribute a blind reading,
    rather than being silently invisible to the dew-point scan.  Uses the
    REAL DewPointScanner (no stub_scan) so the merge logic is exercised
    end-to-end; "living" has no humidity_sensor of its own so it only serves
    to keep cooling active without competing in the worst-source selection.
    """

    def test_unresolvable_mode_zone_pulls_target_to_blind_floor_while_another_zone_cools(self):
        all_zones = {
            "living": {"climate_entity_id": "climate.living"},
            "attic": {"climate_entity_id": "climate.attic", "humidity_sensor": "sensor.attic_humidity"},
        }
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": all_zones["living"]}},
            all_zones=all_zones,
            states={COOL_ENTITY: number_state(22.0)},
            # "climate.attic" deliberately absent from states: hass.states.get
            # returns None for it, i.e. genuinely unresolvable (not "off"/"heat").
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        targets = controller.compute_targets(NOW)

        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(WATER_TEMP_BLIND_MIN_SUPPLY)
        assert controller.diagnostics()["worst_source"] == "attic"

    def test_resolvable_but_non_cool_zone_does_not_contribute(self):
        """A zone that resolves fine (just not to "cool") is correctly excluded."""
        all_zones = {
            "living": {"climate_entity_id": "climate.living"},
            "bedroom": {"climate_entity_id": "climate.bedroom", "humidity_sensor": "sensor.bedroom_humidity"},
        }
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": all_zones["living"]}},
            all_zones=all_zones,
            states={
                COOL_ENTITY: number_state(22.0),
                "climate.bedroom": climate_state("heat"),  # resolvable -> genuinely not cooling
            },
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        targets = controller.compute_targets(NOW)

        # No dew-point source at all (living has none, bedroom correctly
        # excluded) -> scanner's own "no sources" blind floor, not "bedroom".
        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(WATER_TEMP_BLIND_MIN_SUPPLY)
        assert controller.diagnostics()["worst_source"] is None

    def test_no_contribution_when_cooling_is_not_active(self):
        all_zones = {
            "living": {"climate_entity_id": "climate.living"},
            "attic": {"climate_entity_id": "climate.attic", "humidity_sensor": "sensor.attic_humidity"},
        }
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {}},  # nothing resolved to COOL
            all_zones=all_zones,
            states={COOL_ENTITY: number_state(22.0)},
        )

        assert WATER_TEMP_MODE_COOLING not in controller.compute_targets(NOW)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
