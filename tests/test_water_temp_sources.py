"""Tests for the water-temperature dew point source scanner."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from custom_components.adaptive_climate.const import WATER_TEMP_BLIND_MIN_SUPPLY
from custom_components.adaptive_climate.managers.water_temp_sources import (
    DewPointScanner,
)

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def make_state(value, attributes=None, last_updated=NOW):
    state = MagicMock()
    state.state = value
    state.attributes = attributes or {}
    state.last_updated = last_updated
    return state


class FakeWorld:
    """Minimal hass/coordinator double driven by a plain dict of states."""

    def __init__(self):
        self.states_map: dict[str, MagicMock] = {}
        self.zones: dict[str, dict] = {}
        self.hass = MagicMock()
        self.hass.states.get = self.states_map.get
        self.coordinator = MagicMock()
        self.coordinator.get_zones_in_mode = lambda mode: self.zones
        self.coordinator.get_zone_current_temp = self._zone_temp

    def _zone_temp(self, zone_id):
        zone = self.zones.get(zone_id, {})
        state = self.states_map.get(zone.get("climate_entity_id", ""))
        if state is None:
            return None
        temp = state.attributes.get("current_temperature")
        return float(temp) if isinstance(temp, (int, float)) else None

    def add_zone(self, zone_id, *, humidity, rh, room_temp, exclude=False, overrides=None, rh_updated=NOW):
        entity = f"climate.{zone_id}"
        self.zones[zone_id] = {
            "climate_entity_id": entity,
            "humidity_sensor": humidity,
            "exclude_from_dew_point": exclude,
        }
        self.states_map[entity] = make_state(
            "cool",
            {
                "current_temperature": room_temp,
                "status": {"overrides": overrides or []},
            },
        )
        if humidity is not None:
            self.states_map[humidity] = make_state(str(rh), last_updated=rh_updated)

    def scanner(self, extra_sensors=None, fallback_humidity=65.0):
        return DewPointScanner(
            self.hass,
            self.coordinator,
            extra_sensors=extra_sensors or [],
            fallback_humidity=fallback_humidity,
        )


# --- worst-source selection ------------------------------------------------


def test_worst_source_is_the_highest_dew_point():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=50.0, room_temp=24.0)
    world.add_zone("kitchen", humidity="sensor.kitchen_rh", rh=70.0, room_temp=24.0)

    scan = world.scanner().scan(NOW)

    assert scan.blind is False
    assert scan.worst_source == "kitchen"
    # dew_point(24.0, 70.0) via Magnus-Tetens (verified against Task 1's dew_point() helper).
    assert scan.dew_point == pytest.approx(18.19, abs=0.05)


def test_extra_sensors_are_scanned_regardless_of_mode():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=45.0, room_temp=24.0)
    world.states_map["sensor.manifold_rh"] = make_state("85")
    world.states_map["sensor.manifold_temp"] = make_state("18")

    scan = world.scanner(
        extra_sensors=[{"humidity": "sensor.manifold_rh", "temperature": "sensor.manifold_temp"}]
    ).scan(NOW)

    assert scan.worst_source == "extra:sensor.manifold_rh"
    assert scan.dew_point == pytest.approx(15.5, abs=0.2)


def test_zones_without_a_humidity_sensor_are_skipped():
    world = FakeWorld()
    world.add_zone("living", humidity=None, rh=None, room_temp=24.0)
    world.add_zone("kitchen", humidity="sensor.kitchen_rh", rh=55.0, room_temp=24.0)

    scan = world.scanner().scan(NOW)

    assert [r.key for r in scan.readings] == ["kitchen"]


# --- exclusions ------------------------------------------------------------


def test_excluded_zone_is_omitted():
    world = FakeWorld()
    world.add_zone("bathroom", humidity="sensor.bath_rh", rh=90.0, room_temp=24.0, exclude=True)
    world.add_zone("living", humidity="sensor.living_rh", rh=50.0, room_temp=24.0)

    scan = world.scanner().scan(NOW)

    assert [r.key for r in scan.readings] == ["living"]


@pytest.mark.parametrize("humidity_state", ["paused", "stabilizing"])
def test_humidity_paused_zone_is_omitted(humidity_state):
    """A shower in progress is local and transient — the detector already knows."""
    world = FakeWorld()
    world.add_zone(
        "bathroom",
        humidity="sensor.bath_rh",
        rh=95.0,
        room_temp=24.0,
        overrides=[{"type": "humidity", "state": humidity_state}],
    )
    world.add_zone("living", humidity="sensor.living_rh", rh=50.0, room_temp=24.0)

    scan = world.scanner().scan(NOW)

    assert [r.key for r in scan.readings] == ["living"]


# --- temperature pairing ---------------------------------------------------


def test_temp_pairing_prefers_a_sensor_on_the_same_device():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=60.0, room_temp=19.0)
    world.states_map["sensor.living_device_temp"] = make_state("26.0")

    scanner = world.scanner()
    scanner._find_paired_temp_entity = lambda _entity_id: "sensor.living_device_temp"
    scan = scanner.scan(NOW)

    reading = scan.readings[0]
    assert reading.temp_source == "device"
    assert reading.temp_c == pytest.approx(26.0)


def test_temp_pairing_falls_back_to_zone_current_temperature():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=60.0, room_temp=25.0)

    scanner = world.scanner()
    scanner._find_paired_temp_entity = lambda _entity_id: None
    scan = scanner.scan(NOW)

    reading = scan.readings[0]
    assert reading.temp_source == "climate"
    assert reading.temp_c == pytest.approx(25.0)


def test_extra_sensor_pair_uses_the_configured_temperature_entity():
    world = FakeWorld()
    world.states_map["sensor.manifold_rh"] = make_state("70")
    world.states_map["sensor.manifold_temp"] = make_state("17.5")

    scan = world.scanner(
        extra_sensors=[{"humidity": "sensor.manifold_rh", "temperature": "sensor.manifold_temp"}]
    ).scan(NOW)

    assert scan.readings[0].temp_source == "entity"
    assert scan.readings[0].temp_c == pytest.approx(17.5)


# --- plausibility ----------------------------------------------------------


@pytest.mark.parametrize("rh", [0.0, 1.0, 101.0])
def test_implausible_rh_uses_fallback_humidity(rh):
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=rh, room_temp=24.0)

    scan = world.scanner(fallback_humidity=65.0).scan(NOW)

    reading = scan.readings[0]
    assert reading.rh_pct == pytest.approx(65.0)
    assert reading.real is False


@pytest.mark.parametrize("room_temp", [3.0, 45.0])
def test_implausible_temperature_drops_the_source(room_temp):
    """No usable temperature means no computable dew point for that source."""
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=55.0, room_temp=room_temp)

    scan = world.scanner().scan(NOW)

    assert scan.readings == ()
    assert scan.blind is True


# --- staleness -------------------------------------------------------------


def test_stale_reading_uses_max_of_last_ema_and_fallback():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=80.0, room_temp=24.0)
    scanner = world.scanner(fallback_humidity=65.0)

    scanner.scan(NOW)  # seeds the EMA at 80%

    world.states_map["sensor.living_rh"] = make_state("80", last_updated=NOW - timedelta(minutes=120))
    scan = scanner.scan(NOW + timedelta(minutes=5))

    reading = scan.readings[0]
    assert reading.rh_pct == pytest.approx(80.0)  # last EMA beats the 65% fallback
    assert reading.real is False


def test_stale_reading_with_no_history_uses_fallback():
    world = FakeWorld()
    world.add_zone(
        "living",
        humidity="sensor.living_rh",
        rh=40.0,
        room_temp=24.0,
        rh_updated=NOW - timedelta(minutes=90),
    )

    scan = world.scanner(fallback_humidity=65.0).scan(NOW)

    assert scan.readings[0].rh_pct == pytest.approx(65.0)
    assert scan.readings[0].real is False


# --- EMA smoothing ---------------------------------------------------------


def test_ema_damps_a_single_humidity_spike():
    """One shower must not lock out house-wide cooling."""
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=50.0, room_temp=24.0)
    scanner = world.scanner()

    first = scanner.scan(NOW)
    assert first.readings[0].rh_pct == pytest.approx(50.0)  # first sample seeds

    world.states_map["sensor.living_rh"] = make_state("90")
    second = scanner.scan(NOW + timedelta(minutes=5))

    assert 50.0 < second.readings[0].rh_pct < 70.0


def test_ema_converges_toward_a_sustained_level():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=50.0, room_temp=24.0)
    scanner = world.scanner()
    scanner.scan(NOW)

    last = 50.0
    for minutes in range(5, 125, 5):
        # Refresh last_updated alongside `now` each step — a sensor that keeps
        # reporting 70% stays fresh; WATER_TEMP_STALE_MINUTES=60 would otherwise
        # freeze the EMA partway through this >60-minute convergence window.
        world.states_map["sensor.living_rh"] = make_state("70", last_updated=NOW + timedelta(minutes=minutes))
        scan = scanner.scan(NOW + timedelta(minutes=minutes))
        assert scan.readings[0].rh_pct >= last
        last = scan.readings[0].rh_pct

    assert last == pytest.approx(70.0, abs=0.5)


# --- blind mode ------------------------------------------------------------


def test_blind_when_every_source_is_fallback_only():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=0.0, room_temp=24.0)

    scan = world.scanner().scan(NOW)

    assert scan.blind is True
    assert scan.dew_point is not None  # still computed from the fallback


def test_blind_when_no_sources_at_all():
    world = FakeWorld()

    scan = world.scanner().scan(NOW)

    assert scan.blind is True
    assert scan.dew_point is None
    assert scan.worst_source is None


def test_not_blind_when_at_least_one_real_reading_exists():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=0.0, room_temp=24.0)
    world.add_zone("kitchen", humidity="sensor.kitchen_rh", rh=55.0, room_temp=24.0)

    scan = world.scanner().scan(NOW)

    assert scan.blind is False


# --- review finding #8: unresolvable zone temperature must not be silently dropped ----


def test_zone_with_unresolvable_temperature_contributes_a_blind_reading():
    """A registered COOL zone whose temperature can't be resolved (renamed/suffixed
    entity, unavailable sensor, ...) must still contribute — as a non-real reading
    pinned to the system's blind floor — rather than being silently skipped, which
    would drop that room's humidity signal from the scan entirely and could let the
    supply water run below its actual dew point.
    """
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=50.0, room_temp=24.0)
    # "kitchen" is a registered, in-mode COOL zone with a humidity sensor, but its
    # climate entity has no usable current_temperature (e.g. temp sensor down) and
    # there is no device-paired temperature sensor either.
    world.add_zone("kitchen", humidity="sensor.kitchen_rh", rh=90.0, room_temp=None)

    scanner = world.scanner()
    scanner._find_paired_temp_entity = lambda _entity_id: None
    scan = scanner.scan(NOW)

    assert {r.key for r in scan.readings} == {"living", "kitchen"}
    kitchen_reading = next(r for r in scan.readings if r.key == "kitchen")
    assert kitchen_reading.real is False
    assert kitchen_reading.dew_point_c == pytest.approx(WATER_TEMP_BLIND_MIN_SUPPLY)
    assert kitchen_reading.temp_source == "climate"


def test_unresolvable_zone_temperature_does_not_force_blind_when_another_zone_is_real():
    """The unresolvable zone contributes its floor value but must not, by itself,
    force the whole scan blind when another zone has a genuine reading.
    """
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=50.0, room_temp=24.0)
    world.add_zone("kitchen", humidity="sensor.kitchen_rh", rh=90.0, room_temp=None)

    scanner = world.scanner()
    scanner._find_paired_temp_entity = lambda _entity_id: None
    scan = scanner.scan(NOW)

    assert scan.blind is False


def test_unresolvable_zone_temperature_can_win_worst_source():
    """When every other zone's dew point is below the blind floor, the unresolvable
    zone's conservative floor value must still be able to win worst-source selection
    — this is what actually protects the supply water from running too cold.
    """
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=30.0, room_temp=18.0)
    world.add_zone("kitchen", humidity="sensor.kitchen_rh", rh=90.0, room_temp=None)

    scanner = world.scanner()
    scanner._find_paired_temp_entity = lambda _entity_id: None
    scan = scanner.scan(NOW)

    assert scan.worst_source == "kitchen"
    assert scan.dew_point == pytest.approx(WATER_TEMP_BLIND_MIN_SUPPLY)
