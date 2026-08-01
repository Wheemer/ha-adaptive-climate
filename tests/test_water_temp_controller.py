"""Tests for WaterTempController: targets, ramps, writes, interlocks, gate."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.adaptive_climate.const import (
    WATER_TEMP_BINDING_BLIND,
    WATER_TEMP_BINDING_DEW_POINT,
    WATER_TEMP_BINDING_ENTITY_LIMIT,
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

    def test_blind_mode_dew_target_floors_rather_than_replaces_a_high_degraded_reading(self):
        """Blind mode is a FLOOR on the degraded (fallback-humidity) dew point,
        not a flat replacement of it (review finding: blind path). The bound
        actually binds here: dew_point(21.0) + margin(2.0) = 23.0, which is
        ABOVE both min_supply_temp(18.0) and WATER_TEMP_BLIND_MIN_SUPPLY(20.0)
        — the old code discarded this and returned 20.0, an unsafe target
        colder than condensation safety actually requires.
        """
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(24.0)},
        )
        stub_scan(controller, dew_point=21.0, blind=True)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        targets = controller.compute_targets(NOW)

        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(23.0)
        assert controller.binding[WATER_TEMP_MODE_COOLING] == WATER_TEMP_BINDING_BLIND

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

        # Intermediate ticks (production recomputes every 5 min, always well
        # under idle_days=7) keep last_active fresh so this multi-day jump
        # doesn't itself look like a fresh idle gap and spuriously restart
        # the ramp (the stale-ramp fix is keyed on last_active staleness).
        for day in (3, 6, 9):
            controller.compute_targets(NOW + timedelta(days=day))
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
        # Intermediate tick (see comment above) before the jump to day 10.
        controller.compute_targets(NOW + timedelta(days=6))
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

    def test_stale_ramp_restarts_after_a_mid_ramp_idle_gap_instead_of_completing_in_one_step(self):
        """Review finding: a ramp interrupted mid-flight by a long idle gap
        (mode deactivated before the ramp finished, off-season passes,
        reactivated) must restart fresh, not compute an enormous elapsed
        time against the stale ramp_started and land the full step in one
        write. The bound actually binds: ramp_started is 40 days stale here,
        vastly exceeding idle_days(7), so the old code's
        ``ramp.ramp_started is None`` guard incorrectly skipped the restart.
        """
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(18.0)},
        )
        stub_scan(controller, dew_point=14.0)  # dew_target floors to min_supply=18.0

        ramp = controller.ramp_state[WATER_TEMP_MODE_COOLING]
        # A ramp started 40 days ago, but the mode went inactive only 1 day
        # in -- last_active is frozen there since _update_ramp is never
        # called while inactive.
        ramp.ramp_started = NOW - timedelta(days=40)
        ramp.ramp_start_value = 22.0
        ramp.last_active = NOW - timedelta(days=39)

        targets = controller.compute_targets(NOW)

        # Restarted fresh from "now" (old code would instead have jumped
        # straight to dew_target=18.0 in one write, with ramp_started left
        # None and binding=min_supply).
        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started == NOW
        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(22.0)
        assert controller.binding[WATER_TEMP_MODE_COOLING] == WATER_TEMP_BINDING_RAMP

    def test_idle_shorter_than_idle_days_preserves_an_in_progress_ramps_own_start(self):
        """Preserve the < idle_days continue-from-own-start behavior even
        with the stale-ramp restart fix: a short gap must not restart an
        already in-progress ramp."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(20.0)},
        )
        stub_scan(controller, dew_point=14.0)

        ramp = controller.ramp_state[WATER_TEMP_MODE_COOLING]
        started = NOW - timedelta(days=2)
        ramp.ramp_started = started
        ramp.ramp_start_value = 22.0
        ramp.last_active = NOW - timedelta(days=1)  # idle 1 day, well under idle_days=7

        controller.compute_targets(NOW)

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

    def test_mid_ramp_cooling_config_change_alters_the_next_computed_value(self):
        """R13 binding test: a live edit to ``ramp_start`` (22 -> 20) takes
        effect on the very next cycle -- no ``.storage`` hand-editing
        required. Previously ``ramp_start_value`` was captured at seed time
        and persisted, making a mid-ramp config change silently ineffective.
        """
        cooling_cfg = cooling_config()  # ramp_start=22.0, ramp_rate=1.0
        controller = build_controller(
            cooling=cooling_cfg,
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0)  # dew_target floors to min_supply=18.0
        controller.compute_targets(NOW)  # ramp seeded at the (then) configured 22.0

        cooling_cfg["ramp_start"] = 20.0  # live config edit, mid-ramp

        targets = controller.compute_targets(NOW + timedelta(days=1))

        # 20.0 - 1.0*1 day = 19.0 -- NOT 21.0 (which the stale persisted
        # ramp_start_value=22.0 would have produced).
        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(19.0)

    def test_heating_mid_ramp_config_raise_applies_while_a_higher_persisted_seed_still_wins(self):
        """R13: heating ramp origin = max(live config ramp_start, persisted
        entity seed). The seed (captured because the entity was already
        running hot -- backup-heater trap) keeps protecting against a config
        drop below it, but a config raise ABOVE the seed takes effect
        immediately, mid-ramp."""
        heating_cfg = heating_config()  # ramp_start=25.0, target=35.0, ramp_rate=2.0
        controller = build_controller(
            heating=heating_cfg,
            zones_in_mode={"heat": {"living": {}}},
            states={HEAT_ENTITY: number_state(33.0)},  # entity running hot -> seed=33.0
        )
        controller.compute_targets(NOW)
        assert controller.ramp_state[WATER_TEMP_MODE_HEATING].ramp_start_value == pytest.approx(33.0)

        heating_cfg["ramp_start"] = 30.0  # still below the seed: seed still wins
        targets = controller.compute_targets(NOW + timedelta(hours=6))  # 0.25 day
        assert targets[WATER_TEMP_MODE_HEATING] == pytest.approx(33.5)  # 33.0 seed + 2.0*0.25

        heating_cfg["ramp_start"] = 34.0  # raised ABOVE the seed: live config now wins
        targets = controller.compute_targets(NOW + timedelta(hours=9))  # 0.375 day
        assert targets[WATER_TEMP_MODE_HEATING] == pytest.approx(34.75)  # 34.0 config + 2.0*0.375


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

    def test_persisted_state_omits_ramp_start_value_for_cooling(self):
        """R13: cooling's ramp origin is read live from config each compute,
        so nothing needs to be persisted for it -- only the heating seed is
        written out."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0)
        controller.compute_targets(NOW)

        state = controller.get_state_for_persistence()

        assert state[WATER_TEMP_MODE_COOLING]["ramp_start_value"] is None

    def test_persisted_state_keeps_ramp_start_value_for_heating(self):
        controller = build_controller(
            heating=heating_config(),
            zones_in_mode={"heat": {"living": {}}},
            states={HEAT_ENTITY: number_state(33.0)},
        )
        controller.compute_targets(NOW)

        state = controller.get_state_for_persistence()

        assert state[WATER_TEMP_MODE_HEATING]["ramp_start_value"] == pytest.approx(33.0)

    def test_old_format_store_ramp_start_value_ignored_for_cooling_used_as_seed_for_heating(self):
        """Migration: old stores persisted ``ramp_start_value`` for both
        modes. Cooling must ignore it on restore (live config is now
        authoritative); heating must still restore it and use it as the
        persisted seed. No storage version bump."""
        old_store = {
            WATER_TEMP_MODE_COOLING: {
                "last_active": NOW.isoformat(),
                "ramp_started": NOW.isoformat(),
                "ramp_start_value": 22.0,
            },
            WATER_TEMP_MODE_HEATING: {
                "last_active": NOW.isoformat(),
                "ramp_started": NOW.isoformat(),
                "ramp_start_value": 33.0,
            },
        }
        controller = build_controller(cooling=cooling_config(), heating=heating_config())

        controller.restore_state(old_store)

        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_start_value is None
        assert controller.ramp_state[WATER_TEMP_MODE_HEATING].ramp_start_value == pytest.approx(33.0)

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
    async def test_heating_unsafe_direction_upward_change_requires_the_dwell_window(self):
        """Review finding #9 leftover: heating's unsafe direction is UP
        (cooler is safer for heating per is_safe_direction) -- mirrors
        test_unsafe_direction_change_requires_the_dwell_window for cooling,
        which only ever exercised the downward (cooling) case."""
        controller = build_controller(
            heating=heating_config(target=35.0, ramp_rate=2.0),
            zones_in_mode={"heat": {"living": {}}},
            states={HEAT_ENTITY: number_state(25.0, step=0.5)},
        )
        ramp = controller.ramp_state[WATER_TEMP_MODE_HEATING]
        ramp.ramp_started = NOW
        ramp.ramp_start_value = 25.0
        ramp.last_active = NOW

        await controller.async_apply(NOW)  # ramp_value=25.0, first write, no baseline
        assert written_values(controller) == [25.0]

        await controller.async_apply(NOW + timedelta(hours=6))  # ramp_value=25.5, upward, held
        assert written_values(controller) == [25.0]

        await controller.async_apply(NOW + timedelta(hours=6, minutes=29))  # < 30 min since held
        assert written_values(controller) == [25.0]

        await controller.async_apply(NOW + timedelta(hours=6, minutes=31))  # >= 30 min -> writes
        assert written_values(controller) == [25.0, 25.5]

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
    async def test_target_entity_with_no_state_skips_the_write(self):
        """Review finding #4: an entity with no state at all (not yet
        loaded, renamed) must be skipped entirely -- not clamped against
        the heating-shaped SUPPLY_TEMP_MIN/MAX (25/80) fallback, which
        would poison _last_written with a bogus value and could mask the
        real target once the entity actually loads. The 5-min timer
        retries on the next cycle."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={},  # COOL_ENTITY deliberately absent -> hass.states.get returns None
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        controller.hass.services.async_call.assert_not_awaited()
        assert controller._last_written.get(COOL_ENTITY) is None

    @pytest.mark.asyncio
    async def test_entity_maximum_below_dew_target_is_flagged_as_entity_limited(self, caplog):
        """Review finding #5: a maximum-clamp that lands the cooling write
        BELOW the dew target must not be silent -- rate-limited WARNING
        plus binding_constraint='entity_limit'. The bound actually binds:
        the entity's max(21.0) is below dew_target(27.0)."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {"climate_entity_id": "climate.living"}}},
            states={COOL_ENTITY: number_state(20.0, minimum=15.0, maximum=21.0)},
        )
        stub_scan(controller, dew_point=25.0)  # dew_target = 25.0 + 2.0 margin = 27.0 > max(21.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        with caplog.at_level(logging.WARNING):
            await controller.async_apply(NOW)

        assert written_values(controller) == [21.0]
        assert controller.diagnostics()["binding_constraint"] == WATER_TEMP_BINDING_ENTITY_LIMIT
        assert any("entity limit" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_entity_minimum_above_heating_target_is_flagged_as_entity_limited(self, caplog):
        """Mirror of the cooling case for heating: a minimum-clamp that
        lands the write ABOVE the heating target (the unsafe direction for
        heating) must also warn and surface binding_constraint='entity_limit'."""
        controller = build_controller(
            heating=heating_config(target=30.0),
            zones_in_mode={"heat": {"living": {}}},
            states={HEAT_ENTITY: number_state(30.0, minimum=32.0, maximum=45.0)},
        )
        controller._ramp[WATER_TEMP_MODE_HEATING].last_active = NOW - timedelta(hours=1)

        with caplog.at_level(logging.WARNING):
            await controller.async_apply(NOW)

        assert written_values(controller) == [32.0]
        assert controller.diagnostics()["binding_constraint"] == WATER_TEMP_BINDING_ENTITY_LIMIT
        assert any("entity limit" in record.message.lower() for record in caplog.records)

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
    async def test_continued_same_direction_drift_keeps_the_original_dwell_anchor(self):
        """Review finding #6: a value that keeps drifting further in the
        same (unsafe) direction must NOT restart the dwell -- only the
        elapsed time since the *original* anchor (when the drift first
        left the last-written band) matters. Held here only because 20 min
        have passed since that original anchor at minute 20, not because
        anything "restarted" (a genuine reversal restarting the dwell is
        covered by test_dwell_only_resets_on_a_genuine_direction_reversal)."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(21.0)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        stub_scan(controller, dew_point=19.0)
        await controller.async_apply(NOW)  # writes 21.0, first write
        stub_scan(controller, dew_point=17.0)
        await controller.async_apply(NOW + timedelta(minutes=20))  # 19.0 -- dwell anchor starts here
        stub_scan(controller, dew_point=16.0)  # 18.0 -- further in the same unsafe direction
        await controller.async_apply(NOW + timedelta(minutes=25))
        await controller.async_apply(NOW + timedelta(minutes=40))  # 20 min since the anchor at minute 20

        assert written_values(controller) == [21.0]

    @pytest.mark.asyncio
    async def test_dwell_only_resets_on_a_genuine_direction_reversal(self):
        """Review finding #6: unlike continued same-direction drift, a
        value that reverses back toward the safe side (e.g. RH noise
        bouncing the reading back up) DOES restart the dwell from the
        reversal point."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(21.0)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        stub_scan(controller, dew_point=19.0)
        await controller.async_apply(NOW)  # writes 21.0, first write
        stub_scan(controller, dew_point=17.0)
        await controller.async_apply(NOW + timedelta(minutes=5))  # 19.0 -- drift starts (unsafe)
        stub_scan(controller, dew_point=18.0)  # 20.0 -- a reversal back toward the safe side
        await controller.async_apply(NOW + timedelta(minutes=10))

        # Reversal restarted the dwell at minute 10 -- only 25 min have
        # passed by minute 35, short of the 30-min window.
        await controller.async_apply(NOW + timedelta(minutes=35))
        assert written_values(controller) == [21.0]

        await controller.async_apply(NOW + timedelta(minutes=41))  # 31 min since the reversal
        assert written_values(controller) == [21.0, 20.0]

    @pytest.mark.asyncio
    async def test_fine_stepped_ramp_does_not_starve_the_unsafe_direction_dwell_forever(self):
        """Review finding #6: at the reviewer's boundary (entity step=0.1,
        ramp_rate=5.0/day), the rounded value crosses to a new step every
        ~1728s -- just under the 1800s min_write_interval. The old dwell
        logic restarted its timer on every such crossing (any pending-value
        change), so writes would freeze at their initial value forever.
        Ticks every 5 min, matching the real recompute cadence."""
        controller = build_controller(
            cooling=cooling_config(ramp_start=22.0, ramp_rate=5.0, min_supply_temp=1.0),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0, step=0.1, minimum=1.0, maximum=45.0)},
        )
        # dew_target floors to min_supply=1.0 -- the ramp binds for the
        # entire test window, well before it would ever reach that floor.
        stub_scan(controller, dew_point=-10.0)

        await controller.async_apply(NOW)  # first write, no baseline -> writes 22.0 immediately
        for tick in range(1, 19):  # every 5 min out to 90 min
            await controller.async_apply(NOW + timedelta(minutes=5 * tick))

        values = written_values(controller)
        assert len(values) >= 2  # the ramp must have progressed past its first write
        assert values[0] == pytest.approx(22.0)
        assert values[-1] < values[0]  # monotonically toward the safe-side floor, never frozen

    @pytest.mark.asyncio
    async def test_oscillating_but_trending_target_does_not_starve_the_dwell(self):
        """Review finding N3: comparing a new candidate against only the
        immediately-preceding one (not the worst value seen since the
        anchor) lets ANY safe-direction blip reset the dwell -- a target
        that's genuinely trending in the unsafe direction but noisy (e.g.
        dew point wobbling while trending down) then never accumulates 30
        held minutes and freezes after its first write forever (verified:
        a downward trend with a same-magnitude bounce every other sample
        produces exactly one write under the old logic). Reversal must
        instead require moving back from the running most-unsafe extreme
        by more than one entity step, not just from the previous sample.
        """
        controller = build_controller(
            cooling=cooling_config(min_supply_temp=1.0),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(21.0, step=0.5, minimum=1.0, maximum=45.0)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        stub_scan(controller, dew_point=19.0)  # 21.0 -- first write, no baseline
        await controller.async_apply(NOW)

        # Trend down (big step -1.0) with a noise bounce (+0.3) every other
        # 5-min tick -- net progress every cycle, but each bounce is well
        # under one entity step (0.5) from the running extreme so far.
        dew_point = 18.0  # -> final 20.0
        for tick in range(1, 17):  # 5..80 min
            stub_scan(controller, dew_point=dew_point)
            await controller.async_apply(NOW + timedelta(minutes=5 * tick))
            dew_point += 0.3 if tick % 2 else -1.3

        values = written_values(controller)
        assert len(values) >= 3  # more than just the initial write + a single unfreeze
        assert values[-1] < values[0]

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
    async def test_interlock_park_never_lowers_supply_below_the_current_dew_target(self):
        """Spec amendment: interlock park = max(ramp_start, current dew
        target), so an interlock can never LOWER the supply temperature. The
        bound actually binds here: dew_point(25.0) + margin(2.0) = 27.0 is
        ABOVE ramp_start(22.0) -- parking at the bare ramp_start would
        command water colder than condensation safety currently requires.
        """
        states = {COOL_ENTITY: number_state(19.0), "binary_sensor.condensation": binary_state("on")}
        controller = build_controller(
            cooling=cooling_config(),  # ramp_start=22.0, min_supply=18.0, margin=2.0
            zones_in_mode={"cool": {"living": {"climate_entity_id": "climate.living"}}},
            states=states,
            condensation_sensor="binary_sensor.condensation",
        )
        stub_scan(controller, dew_point=25.0)  # 25.0 + 2.0 margin = 27.0 > ramp_start(22.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert written_values(controller) == [27.0]

    def test_interlock_does_not_fast_forward_an_in_progress_ramp(self):
        """Review finding #8: while interlocked the target is parked, not
        progressing -- once the interlock clears, the ramp must resume from
        where it actually was, not from a days_since(ramp_started)
        calculation that counts the entire interlocked span as ramp
        progress. The bound actually binds: without the fix the ramp would
        appear to have advanced ~6 days instead of the real ~1 day and would
        already have ended.
        """
        states = {COOL_ENTITY: number_state(22.0), "binary_sensor.condensation": binary_state("off")}
        controller = build_controller(
            cooling=cooling_config(),  # ramp_start=22.0, ramp_rate=1.0/day
            zones_in_mode={"cool": {"living": {"climate_entity_id": "climate.living"}}},
            states=states,
            condensation_sensor="binary_sensor.condensation",
        )
        stub_scan(controller, dew_point=14.0)  # dew_target floors at min_supply=18.0

        controller.compute_targets(NOW)  # ramp starts fresh (first run)
        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started == NOW

        states["binary_sensor.condensation"] = binary_state("on")
        controller.compute_targets(NOW + timedelta(days=1))  # interlock engages after 1 real ramp day

        states["binary_sensor.condensation"] = binary_state("off")
        controller.compute_targets(NOW + timedelta(days=6))  # first "off" reading starts the dwell
        cleared_cycle = NOW + timedelta(days=6, minutes=31)  # dwell (30 min) elapses -> clears
        controller.compute_targets(cleared_cycle)

        ramp = controller.ramp_state[WATER_TEMP_MODE_COOLING]
        assert controller.binding[WATER_TEMP_MODE_COOLING] == WATER_TEMP_BINDING_RAMP
        assert ramp.ramp_started is not None
        days_elapsed = (cleared_cycle - ramp.ramp_started).total_seconds() / 86400.0
        assert days_elapsed == pytest.approx(1.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_interlock_just_cleared_flag_does_not_leak_into_a_cycle_where_cooling_is_inactive(self):
        """Review finding #10: the one-shot force-write flag must be reset
        at the top of every compute_targets() cycle, not only inside the
        interlock manager's own evaluate() -- which is never reached once
        cooling itself goes inactive, and would otherwise leave a stale
        True flag lying around indefinitely."""
        zones = {"cool": {"living": {"climate_entity_id": "climate.living"}}}
        states = {COOL_ENTITY: number_state(19.0), "binary_sensor.condensation": binary_state("on")}
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode=zones,
            states=states,
            condensation_sensor="binary_sensor.condensation",
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)
        await controller.async_apply(NOW)  # parks, interlock engaged

        states["binary_sensor.condensation"] = binary_state("off")
        await controller.async_apply(NOW + timedelta(minutes=10))  # dwell starts, still holding
        await controller.async_apply(NOW + timedelta(minutes=45))  # dwell elapses -> clears this cycle
        assert controller._interlock.just_cleared is True

        zones["cool"] = {}  # cooling itself goes inactive the very next cycle
        await controller.async_apply(NOW + timedelta(minutes=50))

        assert controller._interlock.just_cleared is False

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
# N1 (BLOCKER): interlock state reset when cooling goes inactive
# =============================================================================


class TestInterlockSeasonalReset:
    """N1 (BLOCKER): interlock bookkeeping must reset when cooling goes
    inactive, or an interlock engaged right at season end freezes the
    interlock's "engaged at" timestamp -- on reactivation months later the
    off-season gap gets misread as the interlock's own held duration,
    last_active gets advanced to ~now, and the seasonal ramp restart (task
    #22 finding #2) is skipped with a force-write past the dwell.

    Control-vs-interlock pair (mandatory per re-review): whether or not an
    interlock happened to be engaged right when the season ended, both must
    resume identically -- on a fresh ramp, from the configured ramp_start.
    """

    def _run_to_reactivation(self, *, interlock_at_end: bool):
        zones = {"cool": {"living": {"climate_entity_id": "climate.living"}}}
        states = {COOL_ENTITY: number_state(22.0), "binary_sensor.condensation": binary_state("off")}
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode=zones,
            states=states,
            condensation_sensor="binary_sensor.condensation",
        )
        stub_scan(controller, dew_point=14.0)  # dew_target floors to min_supply=18.0
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        controller.compute_targets(NOW)  # normal cooling cycle, no ramp needed yet

        if interlock_at_end:
            states["binary_sensor.condensation"] = binary_state("on")
            controller.compute_targets(NOW + timedelta(minutes=5))  # interlock engages, still active

        # Season ends: zones leave cool mode (and, incidentally, whatever
        # triggered the interlock clears too).
        states["binary_sensor.condensation"] = binary_state("off")
        zones["cool"] = {}
        controller.compute_targets(NOW + timedelta(minutes=10))  # one inactive cycle

        zones["cool"] = {"living": {"climate_entity_id": "climate.living"}}

        later = NOW + timedelta(days=180)
        controller.compute_targets(later)  # reactivation
        # A second cycle lets any stale interlock "clear" run its full
        # course (30-min stabilization) -- the fullest exercise of the bug.
        controller.compute_targets(later + timedelta(minutes=31))
        return controller, later

    def test_control_resumes_on_a_fresh_ramp_without_an_interlock(self):
        controller, later = self._run_to_reactivation(interlock_at_end=False)

        ramp = controller.ramp_state[WATER_TEMP_MODE_COOLING]
        assert ramp.ramp_started == later
        assert controller.binding[WATER_TEMP_MODE_COOLING] == WATER_TEMP_BINDING_RAMP

    def test_interlock_at_season_end_still_resumes_on_the_same_fresh_ramp(self):
        """The bound actually binds: without the N1 reset, this diverges
        from the control -- the ~180-day off-season gap gets counted as
        the interlock's held duration instead of a genuine idle gap, and
        the seasonal ramp restart never fires."""
        controller, later = self._run_to_reactivation(interlock_at_end=True)

        ramp = controller.ramp_state[WATER_TEMP_MODE_COOLING]
        assert ramp.ramp_started == later
        assert controller.binding[WATER_TEMP_MODE_COOLING] == WATER_TEMP_BINDING_RAMP

    def test_interlock_clearing_logs_the_held_duration(self, caplog):
        """R12 note #1: the operator-visible INFO log on the clearing
        transition must name the duration that was credited to the ramp,
        not just announce that clearing happened."""
        states = {COOL_ENTITY: number_state(19.0), "binary_sensor.condensation": binary_state("on")}
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {"climate_entity_id": "climate.living"}}},
            states=states,
            condensation_sensor="binary_sensor.condensation",
        )
        stub_scan(controller, dew_point=14.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)
        controller.compute_targets(NOW)  # interlock engages

        states["binary_sensor.condensation"] = binary_state("off")
        controller.compute_targets(NOW + timedelta(minutes=10))  # dwell starts
        with caplog.at_level(logging.INFO):
            controller.compute_targets(NOW + timedelta(minutes=45))  # clears this cycle

        assert any(
            "cooling interlock cleared" in record.message.lower() and "min" in record.message.lower()
            for record in caplog.records
        )

    def test_interlock_reset_clears_the_just_cleared_flag_too(self):
        """R12 note #3: reset() must be self-contained -- clearing
        just_cleared itself rather than relying on the controller's
        compute_targets() having already zeroed it first (a non-local
        invariant the reviewer flagged as fragile)."""
        controller = build_controller(cooling=cooling_config())
        controller._interlock.just_cleared = True

        controller._interlock.reset()

        assert controller._interlock.just_cleared is False


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

    def test_gate_reengages_then_closes_after_a_stale_ramp_reseeds(self):
        """Reviewer 2b: once a stale ramp re-seeds on reactivation, the gate
        must reflect the fresh ramp (open while it runs, closing once it
        legitimately completes) rather than staying wedged on the stale
        pre-off-season state."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(18.0)},
        )
        stub_scan(controller, dew_point=14.0)  # dew_target floors to min_supply=18.0

        ramp = controller.ramp_state[WATER_TEMP_MODE_COOLING]
        ramp.ramp_started = NOW - timedelta(days=40)
        ramp.ramp_start_value = 22.0
        ramp.last_active = NOW - timedelta(days=39)

        controller.compute_targets(NOW)
        assert controller.learning_gate("cool") is True  # fresh ramp just (re)started

        # Past the new ~4-day ramp (22.0 -> 18.0 at 1.0/day), but the gap
        # itself stays well under idle_days=7 so it can't look like *another*
        # fresh idle gap (production ticks every 5 min; see comment on the
        # ramp-completion tests above).
        controller.compute_targets(NOW + timedelta(days=5))
        assert controller.learning_gate("cool") is False  # closes once the new ramp legitimately ends

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

        # The unresolvable-zone placeholder pins temp=dew_point=
        # WATER_TEMP_BLIND_MIN_SUPPLY (worst case: 100% RH at the floor
        # temperature) -- the fixed blind-path formula (review finding:
        # the blind floor must be a FLOOR, not a flat replacement) still
        # layers dew_point_margin on top of that worst-case estimate like
        # any other source, landing at floor + margin rather than the bare
        # floor. Still strictly safer (never lower) than the old behavior.
        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(
            WATER_TEMP_BLIND_MIN_SUPPLY + cooling_config()["dew_point_margin"]
        )
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
