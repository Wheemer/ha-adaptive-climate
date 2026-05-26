"""Focused performance sensor tests: on-time calculation, pruning, chatter filtering.

Covers gaps not in test_performance_sensors.py:
- DutyCycleSensor._calculate_on_time with fixed timestamps (pure logic)
- DutyCycleSensor._prune_old_state_changes correctness
- CycleTimeSensor: sub-minute cycles (chatter) are filtered out
- DutyCycleSensor: multi-segment on/off duty fraction accuracy
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# homeassistant.components.sensor is NOT added by conftest.py.
# Inject it before any import from custom_components.adaptive_climate.sensors.
# ---------------------------------------------------------------------------
if "homeassistant.components.sensor" not in sys.modules:
    _mock_sensor_mod = MagicMock()
    _mock_sensor_mod.SensorEntity = type("SensorEntity", (), {})
    _mock_sensor_mod.SensorDeviceClass = MagicMock()
    _mock_sensor_mod.SensorStateClass = MagicMock()
    sys.modules["homeassistant.components.sensor"] = _mock_sensor_mod

import pytest
from collections import deque
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from custom_components.adaptive_climate.sensors.performance import (
    DutyCycleSensor,
    CycleTimeSensor,
    HeaterStateChange,
    DEFAULT_ROLLING_AVERAGE_SIZE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc(h: int = 0, m: int = 0, s: int = 0) -> datetime:
    """Return a UTC datetime on 2025-01-01 at the given h:m:s."""
    return datetime(2025, 1, 1, h, m, s, tzinfo=timezone.utc)


def _make_duty_sensor() -> DutyCycleSensor:
    hass = Mock()
    hass.states = Mock()
    hass.data = {}
    return DutyCycleSensor(hass=hass, zone_id="z1", zone_name="Zone 1", climate_entity_id="climate.z1")


def _make_cycle_sensor() -> CycleTimeSensor:
    hass = Mock()
    hass.states = Mock()
    hass.data = {}
    return CycleTimeSensor(hass=hass, zone_id="z1", zone_name="Zone 1", climate_entity_id="climate.z1")


# ---------------------------------------------------------------------------
# DutyCycleSensor._calculate_on_time
# ---------------------------------------------------------------------------


class TestCalculateOnTime:
    """_calculate_on_time must sum ON segments within the window precisely."""

    def test_always_on_returns_full_window(self):
        """Single ON before window → full 3 600 s on-time."""
        sensor = _make_duty_sensor()
        ws, we = _utc(9, 0, 0), _utc(10, 0, 0)
        sensor._state_changes = deque([HeaterStateChange(timestamp=_utc(8, 0, 0), is_on=True)])
        assert sensor._calculate_on_time(ws, we) == pytest.approx(3600.0)

    def test_always_off_returns_zero(self):
        """Single OFF before window → zero on-time."""
        sensor = _make_duty_sensor()
        ws, we = _utc(9, 0, 0), _utc(10, 0, 0)
        sensor._state_changes = deque([HeaterStateChange(timestamp=_utc(8, 0, 0), is_on=False)])
        assert sensor._calculate_on_time(ws, we) == pytest.approx(0.0)

    def test_on_for_first_half(self):
        """ON before window, OFF at midpoint → 50 % of window."""
        sensor = _make_duty_sensor()
        ws, we = _utc(9, 0, 0), _utc(10, 0, 0)
        sensor._state_changes = deque(
            [
                HeaterStateChange(timestamp=_utc(8, 0, 0), is_on=True),  # on before window
                HeaterStateChange(timestamp=_utc(9, 30, 0), is_on=False),  # off at midpoint
            ]
        )
        assert sensor._calculate_on_time(ws, we) == pytest.approx(1800.0)

    def test_two_equal_on_segments(self):
        """Two 15-minute ON segments in a 60-minute window → 1 800 s total."""
        sensor = _make_duty_sensor()
        ws, we = _utc(9, 0, 0), _utc(10, 0, 0)
        sensor._state_changes = deque(
            [
                HeaterStateChange(timestamp=_utc(9, 0, 0), is_on=True),
                HeaterStateChange(timestamp=_utc(9, 15, 0), is_on=False),
                HeaterStateChange(timestamp=_utc(9, 30, 0), is_on=True),
                HeaterStateChange(timestamp=_utc(9, 45, 0), is_on=False),
            ]
        )
        assert sensor._calculate_on_time(ws, we) == pytest.approx(1800.0)

    def test_still_on_at_window_end(self):
        """Heater turns ON 10 min before window_end → 600 s counted."""
        sensor = _make_duty_sensor()
        ws, we = _utc(9, 0, 0), _utc(10, 0, 0)
        sensor._state_changes = deque([HeaterStateChange(timestamp=_utc(9, 50, 0), is_on=True)])
        assert sensor._calculate_on_time(ws, we) == pytest.approx(600.0)

    def test_empty_changes_returns_zero(self):
        sensor = _make_duty_sensor()
        sensor._state_changes = deque()
        assert sensor._calculate_on_time(_utc(9), _utc(10)) == 0.0

    def test_change_at_window_start_counts_full_window(self):
        """State change precisely at window_start → entire window is on-time."""
        sensor = _make_duty_sensor()
        ws, we = _utc(9, 0, 0), _utc(10, 0, 0)
        sensor._state_changes = deque([HeaterStateChange(timestamp=ws, is_on=True)])
        assert sensor._calculate_on_time(ws, we) == pytest.approx(3600.0)

    def test_25_percent_duty(self):
        """ON for 15 of 60 minutes → 25 % duty."""
        sensor = _make_duty_sensor()
        ws, we = _utc(9, 0, 0), _utc(10, 0, 0)
        sensor._state_changes = deque(
            [
                HeaterStateChange(timestamp=_utc(9, 0, 0), is_on=True),
                HeaterStateChange(timestamp=_utc(9, 15, 0), is_on=False),
            ]
        )
        on_time = sensor._calculate_on_time(ws, we)
        duty = (on_time / 3600.0) * 100.0
        assert duty == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# DutyCycleSensor._prune_old_state_changes
# ---------------------------------------------------------------------------


class TestPruneOldStateChanges:
    """_prune_old_state_changes keeps one reference before window + all in-window entries."""

    def test_keeps_most_recent_before_window(self):
        """Two old changes → only the later one survives as reference."""
        sensor = _make_duty_sensor()
        ws = _utc(9, 0, 0)
        sensor._state_changes = deque(
            [
                HeaterStateChange(timestamp=_utc(7, 0, 0), is_on=True),  # older
                HeaterStateChange(timestamp=_utc(8, 0, 0), is_on=False),  # newer ← keep
            ]
        )
        sensor._prune_old_state_changes(ws)
        remaining = list(sensor._state_changes)
        assert len(remaining) == 1
        assert remaining[0].timestamp == _utc(8, 0, 0)
        assert remaining[0].is_on is False

    def test_all_in_window_preserved(self):
        """Changes all inside the window: none pruned."""
        sensor = _make_duty_sensor()
        ws = _utc(9, 0, 0)
        sensor._state_changes = deque(
            [
                HeaterStateChange(timestamp=_utc(9, 10, 0), is_on=True),
                HeaterStateChange(timestamp=_utc(9, 25, 0), is_on=False),
                HeaterStateChange(timestamp=_utc(9, 45, 0), is_on=True),
            ]
        )
        sensor._prune_old_state_changes(ws)
        assert len(sensor._state_changes) == 3

    def test_empty_stays_empty(self):
        sensor = _make_duty_sensor()
        sensor._state_changes = deque()
        sensor._prune_old_state_changes(_utc(9))
        assert len(sensor._state_changes) == 0

    def test_mixed_keeps_reference_and_in_window(self):
        """Old and new mixed: reference + all in-window entries kept."""
        sensor = _make_duty_sensor()
        ws = _utc(9, 0, 0)
        sensor._state_changes = deque(
            [
                HeaterStateChange(timestamp=_utc(7, 0, 0), is_on=True),
                HeaterStateChange(timestamp=_utc(8, 30, 0), is_on=False),  # most recent before ws
                HeaterStateChange(timestamp=_utc(9, 15, 0), is_on=True),
                HeaterStateChange(timestamp=_utc(9, 45, 0), is_on=False),
            ]
        )
        sensor._prune_old_state_changes(ws)
        remaining = list(sensor._state_changes)
        assert len(remaining) == 3
        timestamps = {r.timestamp for r in remaining}
        assert _utc(8, 30, 0) in timestamps
        assert _utc(9, 15, 0) in timestamps
        assert _utc(9, 45, 0) in timestamps

    def test_all_before_window_keeps_most_recent(self):
        """All changes before window_start: only the latest survives."""
        sensor = _make_duty_sensor()
        ws = _utc(9, 0, 0)
        sensor._state_changes = deque(
            [
                HeaterStateChange(timestamp=_utc(6, 0, 0), is_on=True),
                HeaterStateChange(timestamp=_utc(7, 0, 0), is_on=False),
                HeaterStateChange(timestamp=_utc(8, 0, 0), is_on=True),  # most recent
            ]
        )
        sensor._prune_old_state_changes(ws)
        remaining = list(sensor._state_changes)
        assert len(remaining) == 1
        assert remaining[0].timestamp == _utc(8, 0, 0)


# ---------------------------------------------------------------------------
# CycleTimeSensor — chatter detection
# ---------------------------------------------------------------------------


class TestChatterFiltering:
    """Sub-minute on/off cycles (chatter) must not be recorded in _cycle_times."""

    def _fire_on_event(self, sensor: CycleTimeSensor, now: datetime) -> None:
        """Simulate heater turning ON at `now`."""
        event = Mock()
        event.data = {"new_state": Mock(state="on")}
        with patch("custom_components.adaptive_climate.sensors.performance.dt_util") as mock_dt:
            mock_dt.utcnow.return_value = now
            sensor._async_heater_state_changed(event)

    def test_sub_minute_cycle_not_recorded(self):
        """30-second cycle must not appear in _cycle_times."""
        sensor = _make_cycle_sensor()
        sensor._current_heater_state = False
        sensor._last_on_timestamp = _utc(10, 0, 0)
        self._fire_on_event(sensor, _utc(10, 0, 30))  # only 30 s later
        assert len(sensor._cycle_times) == 0

    def test_exactly_one_minute_is_recorded(self):
        """A cycle of exactly 60 seconds sits on the ≥ 1-min boundary and is kept."""
        sensor = _make_cycle_sensor()
        sensor._current_heater_state = False
        sensor._last_on_timestamp = _utc(10, 0, 0)
        self._fire_on_event(sensor, _utc(10, 1, 0))
        assert len(sensor._cycle_times) == 1
        assert sensor._cycle_times[0] == pytest.approx(1.0)

    def test_typical_30min_cycle_recorded(self):
        """A normal 30-minute heating cycle is recorded without issue."""
        sensor = _make_cycle_sensor()
        sensor._current_heater_state = False
        sensor._last_on_timestamp = _utc(9, 0, 0)
        self._fire_on_event(sensor, _utc(9, 30, 0))
        assert len(sensor._cycle_times) == 1
        assert sensor._cycle_times[0] == pytest.approx(30.0)

    def test_five_chatter_cycles_all_ignored(self):
        """Five rapid sub-minute on/off events accumulate 0 cycle records."""
        sensor = _make_cycle_sensor()
        sensor._current_heater_state = False
        base = _utc(10, 0, 0)
        for i in range(5):
            sensor._last_on_timestamp = base + timedelta(seconds=30 * i)
            self._fire_on_event(sensor, base + timedelta(seconds=30 * i + 20))  # 20 s gap
        assert len(sensor._cycle_times) == 0

    def test_rolling_average_respects_maxlen(self):
        """_cycle_times deque never exceeds DEFAULT_ROLLING_AVERAGE_SIZE entries."""
        sensor = _make_cycle_sensor()
        for t in range(DEFAULT_ROLLING_AVERAGE_SIZE + 5):
            sensor._cycle_times.append(float(20 + t))
        assert len(sensor._cycle_times) == DEFAULT_ROLLING_AVERAGE_SIZE

    def test_first_on_event_initialises_timestamp_no_cycle(self):
        """If last_on_timestamp is None, the first ON just sets the timestamp."""
        sensor = _make_cycle_sensor()
        sensor._current_heater_state = False
        sensor._last_on_timestamp = None
        self._fire_on_event(sensor, _utc(10, 0, 0))
        assert len(sensor._cycle_times) == 0
        assert sensor._last_on_timestamp == _utc(10, 0, 0)

    def test_average_cycle_time_multiple_cycles(self):
        """_calculate_average_cycle_time returns the mean of recorded durations."""
        sensor = _make_cycle_sensor()
        sensor._cycle_times = deque([15.0, 20.0, 25.0], maxlen=DEFAULT_ROLLING_AVERAGE_SIZE)
        assert sensor._calculate_average_cycle_time() == pytest.approx(20.0)

    def test_average_cycle_time_single_entry(self):
        sensor = _make_cycle_sensor()
        sensor._cycle_times = deque([45.0], maxlen=DEFAULT_ROLLING_AVERAGE_SIZE)
        assert sensor._calculate_average_cycle_time() == pytest.approx(45.0)

    def test_average_cycle_time_none_when_empty(self):
        sensor = _make_cycle_sensor()
        assert sensor._calculate_average_cycle_time() is None
