"""Tests for cycle metrics recorder."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock

import pytest

from custom_components.adaptive_climate.const import HeatingType
from custom_components.adaptive_climate.managers.cycle_metrics import CycleMetricsRecorder


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.async_create_task = MagicMock()
    return hass


@pytest.fixture
def mock_adaptive_learner():
    """Create a mock adaptive learner."""
    learner = MagicMock()
    learner.add_cycle_metrics = MagicMock()
    learner.update_convergence_tracking = MagicMock()
    learner.update_convergence_confidence = MagicMock()
    learner.is_in_validation_mode = MagicMock(return_value=False)
    return learner


@pytest.fixture
def mock_callbacks():
    """Create mock callback functions."""
    return {
        "get_target_temp": Mock(return_value=20.0),
        "get_current_temp": Mock(return_value=18.0),
        "get_hvac_mode": Mock(return_value="heat"),
        "get_in_grace_period": Mock(return_value=False),
    }


class TestExtendedSettlingWindow:
    """Test extended settling window for slow systems."""

    def test_settling_window_by_heating_type(self, mock_hass, mock_adaptive_learner, mock_callbacks):
        """Settling window varies by heating type."""
        # Create recorder for floor_hydronic (slowest system)
        floor_recorder = CycleMetricsRecorder(
            hass=mock_hass,
            zone_id="test_floor",
            adaptive_learner=mock_adaptive_learner,
            get_target_temp=mock_callbacks["get_target_temp"],
            get_current_temp=mock_callbacks["get_current_temp"],
            get_hvac_mode=mock_callbacks["get_hvac_mode"],
            get_in_grace_period=mock_callbacks["get_in_grace_period"],
            min_cycle_duration_minutes=5,
            heating_type=HeatingType.FLOOR_HYDRONIC,
        )

        # Create recorder for forced_air (fastest system)
        forced_recorder = CycleMetricsRecorder(
            hass=mock_hass,
            zone_id="test_forced",
            adaptive_learner=mock_adaptive_learner,
            get_target_temp=mock_callbacks["get_target_temp"],
            get_current_temp=mock_callbacks["get_current_temp"],
            get_hvac_mode=mock_callbacks["get_hvac_mode"],
            get_in_grace_period=mock_callbacks["get_in_grace_period"],
            min_cycle_duration_minutes=5,
            heating_type=HeatingType.FORCED_AIR,
        )

        # Verify settling windows match const.py expectations
        assert floor_recorder.get_settling_window_minutes() == 60
        assert forced_recorder.get_settling_window_minutes() == 10

    def test_settling_window_defaults_to_30_when_no_heating_type(
        self, mock_hass, mock_adaptive_learner, mock_callbacks
    ):
        """Settling window defaults to 30 minutes when heating_type is None."""
        recorder = CycleMetricsRecorder(
            hass=mock_hass,
            zone_id="test_no_type",
            adaptive_learner=mock_adaptive_learner,
            get_target_temp=mock_callbacks["get_target_temp"],
            get_current_temp=mock_callbacks["get_current_temp"],
            get_hvac_mode=mock_callbacks["get_hvac_mode"],
            get_in_grace_period=mock_callbacks["get_in_grace_period"],
            min_cycle_duration_minutes=5,
            heating_type=None,
        )

        # Should default to 30 minutes (radiator-like default)
        assert recorder.get_settling_window_minutes() == 30

    def test_settling_start_includes_transport_delay(self, mock_hass, mock_adaptive_learner, mock_callbacks):
        """Settling window starts after transport delay."""
        recorder = CycleMetricsRecorder(
            hass=mock_hass,
            zone_id="test_transport",
            adaptive_learner=mock_adaptive_learner,
            get_target_temp=mock_callbacks["get_target_temp"],
            get_current_temp=mock_callbacks["get_current_temp"],
            get_hvac_mode=mock_callbacks["get_hvac_mode"],
            get_in_grace_period=mock_callbacks["get_in_grace_period"],
            min_cycle_duration_minutes=5,
            heating_type=HeatingType.FLOOR_HYDRONIC,
        )

        # Set transport delay (5 minutes)
        recorder.set_transport_delay(5.0)

        # Set device off time
        device_off_time = datetime(2025, 1, 15, 10, 30, 0)
        recorder.set_device_off_time(device_off_time)

        # Get settling start time (should account for transport delay)
        settling_start = recorder.get_settling_start_time()

        # Settling should start 5 minutes after device turned off (transport delay)
        expected_start = datetime(2025, 1, 15, 10, 35, 0)
        assert settling_start == expected_start

    def test_settling_start_includes_valve_actuation(self, mock_hass, mock_adaptive_learner, mock_callbacks):
        """Settling window starts after valve actuation time."""
        recorder = CycleMetricsRecorder(
            hass=mock_hass,
            zone_id="test_valve",
            adaptive_learner=mock_adaptive_learner,
            get_target_temp=mock_callbacks["get_target_temp"],
            get_current_temp=mock_callbacks["get_current_temp"],
            get_hvac_mode=mock_callbacks["get_hvac_mode"],
            get_in_grace_period=mock_callbacks["get_in_grace_period"],
            min_cycle_duration_minutes=5,
            heating_type=HeatingType.FLOOR_HYDRONIC,
            valve_actuation_time=120.0,  # 2 minutes in seconds
        )

        # Set device off time
        device_off_time = datetime(2025, 1, 15, 10, 30, 0)
        recorder.set_device_off_time(device_off_time)

        # Get settling start time (should account for half valve actuation time)
        settling_start = recorder.get_settling_start_time()

        # Settling should start 1 minute after device off (half of 2 min valve time)
        expected_start = datetime(2025, 1, 15, 10, 31, 0)
        assert settling_start == expected_start

    def test_settling_start_includes_both_delays(self, mock_hass, mock_adaptive_learner, mock_callbacks):
        """Settling window starts after both valve actuation and transport delay."""
        recorder = CycleMetricsRecorder(
            hass=mock_hass,
            zone_id="test_both",
            adaptive_learner=mock_adaptive_learner,
            get_target_temp=mock_callbacks["get_target_temp"],
            get_current_temp=mock_callbacks["get_current_temp"],
            get_hvac_mode=mock_callbacks["get_hvac_mode"],
            get_in_grace_period=mock_callbacks["get_in_grace_period"],
            min_cycle_duration_minutes=5,
            heating_type=HeatingType.FLOOR_HYDRONIC,
            valve_actuation_time=120.0,  # 2 minutes in seconds
        )

        # Set transport delay (5 minutes)
        recorder.set_transport_delay(5.0)

        # Set device off time
        device_off_time = datetime(2025, 1, 15, 10, 30, 0)
        recorder.set_device_off_time(device_off_time)

        # Get settling start time (should account for both delays)
        settling_start = recorder.get_settling_start_time()

        # Settling should start 6 minutes after device off:
        # - Half valve actuation: 1 min
        # - Transport delay: 5 min
        expected_start = datetime(2025, 1, 15, 10, 36, 0)
        assert settling_start == expected_start

    def test_settling_start_returns_device_off_when_no_delays(self, mock_hass, mock_adaptive_learner, mock_callbacks):
        """Settling starts at device off time when no delays are present."""
        recorder = CycleMetricsRecorder(
            hass=mock_hass,
            zone_id="test_no_delays",
            adaptive_learner=mock_adaptive_learner,
            get_target_temp=mock_callbacks["get_target_temp"],
            get_current_temp=mock_callbacks["get_current_temp"],
            get_hvac_mode=mock_callbacks["get_hvac_mode"],
            get_in_grace_period=mock_callbacks["get_in_grace_period"],
            min_cycle_duration_minutes=5,
            heating_type=HeatingType.CONVECTOR,
        )

        # Set device off time
        device_off_time = datetime(2025, 1, 15, 10, 30, 0)
        recorder.set_device_off_time(device_off_time)

        # Get settling start time (should be same as device off time)
        settling_start = recorder.get_settling_start_time()

        assert settling_start == device_off_time

    def test_settling_start_returns_none_when_no_device_off(self, mock_hass, mock_adaptive_learner, mock_callbacks):
        """Settling start returns None when device_off_time is not set."""
        recorder = CycleMetricsRecorder(
            hass=mock_hass,
            zone_id="test_no_off",
            adaptive_learner=mock_adaptive_learner,
            get_target_temp=mock_callbacks["get_target_temp"],
            get_current_temp=mock_callbacks["get_current_temp"],
            get_hvac_mode=mock_callbacks["get_hvac_mode"],
            get_in_grace_period=mock_callbacks["get_in_grace_period"],
            min_cycle_duration_minutes=5,
            heating_type=HeatingType.FLOOR_HYDRONIC,
        )

        # Don't set device_off_time

        # Get settling start time (should return None)
        settling_start = recorder.get_settling_start_time()

        assert settling_start is None


class TestRiseTimeThreshold:
    """Test rise_time calculation uses heating-type-specific thresholds."""

    def test_rise_time_uses_floor_hydronic_threshold(self, mock_hass, mock_adaptive_learner, mock_callbacks):
        """Rise time calculation uses 0.5°C threshold for floor_hydronic."""
        from datetime import timedelta
        from unittest.mock import patch

        recorder = CycleMetricsRecorder(
            hass=mock_hass,
            zone_id="test_floor",
            adaptive_learner=mock_adaptive_learner,
            get_target_temp=mock_callbacks["get_target_temp"],
            get_current_temp=mock_callbacks["get_current_temp"],
            get_hvac_mode=mock_callbacks["get_hvac_mode"],
            get_in_grace_period=mock_callbacks["get_in_grace_period"],
            min_cycle_duration_minutes=5,
            cold_tolerance=0.5,
            heating_type=HeatingType.FLOOR_HYDRONIC,
        )

        # Create temperature history reaching target within 0.5°C (but not 0.05°C)
        cycle_start = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        target_temp = 20.0

        temperature_history = [
            (cycle_start, 18.0),
            (cycle_start + timedelta(minutes=10), 18.5),
            (cycle_start + timedelta(minutes=20), 19.0),
            (cycle_start + timedelta(minutes=30), 19.5),
            (cycle_start + timedelta(minutes=40), 19.75),  # Within 0.5°C of target
            (cycle_start + timedelta(minutes=50), 19.8),
        ]

        # Mock calculate_rise_time to capture the threshold parameter
        with patch("custom_components.adaptive_climate.adaptive.cycle_analysis.calculate_rise_time") as mock_calc:
            mock_calc.return_value = 40.0  # 40 minutes to reach target

            # Record cycle metrics (this calls calculate_rise_time internally)
            recorder.record_cycle_metrics(
                cycle_start_time=cycle_start,
                cycle_target_temp=target_temp,
                cycle_state_value="settling",
                temperature_history=temperature_history,
                outdoor_temp_history=[],
            )

            # Verify calculate_rise_time was called with 0.5°C threshold (floor_hydronic)
            mock_calc.assert_called_once()
            call_kwargs = mock_calc.call_args[1]
            assert "threshold" in call_kwargs
            assert call_kwargs["threshold"] == 0.5

    def test_rise_time_uses_forced_air_threshold(self, mock_hass, mock_adaptive_learner, mock_callbacks):
        """Rise time calculation uses 0.15°C threshold for forced_air."""
        from datetime import timedelta
        from unittest.mock import patch

        recorder = CycleMetricsRecorder(
            hass=mock_hass,
            zone_id="test_forced",
            adaptive_learner=mock_adaptive_learner,
            get_target_temp=mock_callbacks["get_target_temp"],
            get_current_temp=mock_callbacks["get_current_temp"],
            get_hvac_mode=mock_callbacks["get_hvac_mode"],
            get_in_grace_period=mock_callbacks["get_in_grace_period"],
            min_cycle_duration_minutes=5,
            cold_tolerance=0.15,
            heating_type=HeatingType.FORCED_AIR,
        )

        # Create temperature history
        cycle_start = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        target_temp = 20.0

        temperature_history = [
            (cycle_start, 18.0),
            (cycle_start + timedelta(minutes=5), 18.5),
            (cycle_start + timedelta(minutes=10), 19.0),
            (cycle_start + timedelta(minutes=15), 19.5),
            (cycle_start + timedelta(minutes=20), 19.9),  # Within 0.15°C of target
        ]

        # Mock calculate_rise_time to capture the threshold parameter
        with patch("custom_components.adaptive_climate.adaptive.cycle_analysis.calculate_rise_time") as mock_calc:
            mock_calc.return_value = 20.0  # 20 minutes to reach target

            # Record cycle metrics
            recorder.record_cycle_metrics(
                cycle_start_time=cycle_start,
                cycle_target_temp=target_temp,
                cycle_state_value="settling",
                temperature_history=temperature_history,
                outdoor_temp_history=[],
            )

            # Verify calculate_rise_time was called with 0.15°C threshold (forced_air)
            mock_calc.assert_called_once()
            call_kwargs = mock_calc.call_args[1]
            assert "threshold" in call_kwargs
            assert call_kwargs["threshold"] == 0.15

    def test_rise_time_defaults_to_0_2_when_no_cold_tolerance(self, mock_hass, mock_adaptive_learner, mock_callbacks):
        """Rise time calculation defaults to 0.2°C threshold when cold_tolerance is None."""
        from datetime import timedelta
        from unittest.mock import patch

        recorder = CycleMetricsRecorder(
            hass=mock_hass,
            zone_id="test_no_type",
            adaptive_learner=mock_adaptive_learner,
            get_target_temp=mock_callbacks["get_target_temp"],
            get_current_temp=mock_callbacks["get_current_temp"],
            get_hvac_mode=mock_callbacks["get_hvac_mode"],
            get_in_grace_period=mock_callbacks["get_in_grace_period"],
            min_cycle_duration_minutes=5,
            heating_type=None,
        )

        # Create temperature history (need at least 5 samples)
        cycle_start = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        target_temp = 20.0

        temperature_history = [
            (cycle_start, 18.0),
            (cycle_start + timedelta(minutes=5), 18.5),
            (cycle_start + timedelta(minutes=10), 19.0),
            (cycle_start + timedelta(minutes=15), 19.5),
            (cycle_start + timedelta(minutes=20), 20.0),
        ]

        # Mock calculate_rise_time to capture the threshold parameter
        with patch("custom_components.adaptive_climate.adaptive.cycle_analysis.calculate_rise_time") as mock_calc:
            mock_calc.return_value = 20.0

            # Record cycle metrics
            recorder.record_cycle_metrics(
                cycle_start_time=cycle_start,
                cycle_target_temp=target_temp,
                cycle_state_value="settling",
                temperature_history=temperature_history,
                outdoor_temp_history=[],
            )

            # Verify calculate_rise_time was called without threshold parameter
            # (will use default 0.2°C from calculate_rise_time function)
            mock_calc.assert_called_once()
            call_kwargs = mock_calc.call_args[1]
            assert "threshold" not in call_kwargs


class TestStartingDeltaCalculation:
    """Test starting_delta calculation for weighted learning."""

    def test_starting_delta_calculated_and_passed_to_cycle_metrics(
        self, mock_hass, mock_adaptive_learner, mock_callbacks
    ):
        """Starting delta is calculated from target_temp - start_temp and passed to CycleMetrics."""
        recorder = CycleMetricsRecorder(
            hass=mock_hass,
            zone_id="test_starting_delta",
            adaptive_learner=mock_adaptive_learner,
            get_target_temp=mock_callbacks["get_target_temp"],
            get_current_temp=mock_callbacks["get_current_temp"],
            get_hvac_mode=mock_callbacks["get_hvac_mode"],
            get_in_grace_period=mock_callbacks["get_in_grace_period"],
            min_cycle_duration_minutes=5,
            heating_type=HeatingType.FLOOR_HYDRONIC,
        )

        # Create temperature history starting at 18.0°C
        start_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        temperature_history = [
            (datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc), 18.0),
            (datetime(2025, 1, 15, 10, 5, 0, tzinfo=timezone.utc), 18.5),
            (datetime(2025, 1, 15, 10, 10, 0, tzinfo=timezone.utc), 19.0),
            (datetime(2025, 1, 15, 10, 15, 0, tzinfo=timezone.utc), 19.5),
            (datetime(2025, 1, 15, 10, 20, 0, tzinfo=timezone.utc), 20.0),
            (datetime(2025, 1, 15, 10, 25, 0, tzinfo=timezone.utc), 20.2),
        ]

        # Target temp is 20.0 (from mock_callbacks)
        # Start temp is 18.0
        # Expected starting_delta = 20.0 - 18.0 = 2.0

        # Record cycle
        recorder.record_cycle_metrics(
            cycle_start_time=start_time,
            cycle_target_temp=20.0,
            cycle_state_value="heating",
            temperature_history=temperature_history,
            outdoor_temp_history=[],
        )

        # Verify add_cycle_metrics was called
        assert mock_adaptive_learner.add_cycle_metrics.call_count == 1

        # Extract the CycleMetrics object that was passed
        call_args = mock_adaptive_learner.add_cycle_metrics.call_args
        cycle_metrics = call_args[0][0]

        # Verify starting_delta is calculated correctly
        assert cycle_metrics.starting_delta == 2.0

    def test_starting_delta_with_cooling_mode(self, mock_hass, mock_adaptive_learner, mock_callbacks):
        """Starting delta is calculated for cooling mode (temp - target)."""
        # Modify callbacks for cooling mode
        mock_callbacks["get_hvac_mode"].return_value = "cool"

        recorder = CycleMetricsRecorder(
            hass=mock_hass,
            zone_id="test_cooling_delta",
            adaptive_learner=mock_adaptive_learner,
            get_target_temp=mock_callbacks["get_target_temp"],
            get_current_temp=mock_callbacks["get_current_temp"],
            get_hvac_mode=mock_callbacks["get_hvac_mode"],
            get_in_grace_period=mock_callbacks["get_in_grace_period"],
            min_cycle_duration_minutes=5,
            heating_type=HeatingType.FORCED_AIR,
        )

        # Create temperature history starting at 22.0°C (above target)
        start_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        temperature_history = [
            (datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc), 22.0),
            (datetime(2025, 1, 15, 10, 5, 0, tzinfo=timezone.utc), 21.5),
            (datetime(2025, 1, 15, 10, 10, 0, tzinfo=timezone.utc), 21.0),
            (datetime(2025, 1, 15, 10, 15, 0, tzinfo=timezone.utc), 20.5),
            (datetime(2025, 1, 15, 10, 20, 0, tzinfo=timezone.utc), 20.0),
            (datetime(2025, 1, 15, 10, 25, 0, tzinfo=timezone.utc), 19.8),
        ]

        # Target temp is 20.0
        # Start temp is 22.0
        # Expected starting_delta = 20.0 - 22.0 = -2.0 (negative because cooling)

        # Record cycle
        recorder.record_cycle_metrics(
            cycle_start_time=start_time,
            cycle_target_temp=20.0,
            cycle_state_value="cooling",
            temperature_history=temperature_history,
            outdoor_temp_history=[],
        )

        # Verify add_cycle_metrics was called
        assert mock_adaptive_learner.add_cycle_metrics.call_count == 1

        # Extract the CycleMetrics object that was passed
        call_args = mock_adaptive_learner.add_cycle_metrics.call_args
        cycle_metrics = call_args[0][0]

        # Verify starting_delta is calculated correctly (target - actual = negative for cooling)
        assert cycle_metrics.starting_delta == -2.0


class TestCycleEndedEventOrdering:
    """Test that CYCLE_ENDED event is emitted before learning save is scheduled (M08)."""

    def test_emit_before_save_scheduling(self, mock_hass, mock_adaptive_learner, mock_callbacks):
        """CYCLE_ENDED event must be emitted BEFORE _schedule_learning_save is called.

        Handlers that mutate the learner (e.g., heating-rate updaters) subscribe to
        CYCLE_ENDED and fire synchronously during emit().  If save is scheduled first,
        the snapshot is taken before those mutations, so learner state is saved stale.

        Fix: emit first, then schedule save.
        """
        from datetime import timedelta
        from unittest.mock import MagicMock

        from custom_components.adaptive_climate.const import DOMAIN
        from custom_components.adaptive_climate.managers.events import (
            CycleEventDispatcher,
            CycleEventType,
        )

        # Track call order using a shared list mutated by side-effects
        call_order: list[str] = []

        # Set up dispatcher with a subscriber that records when emit fires
        dispatcher = CycleEventDispatcher()
        dispatcher.subscribe(
            CycleEventType.CYCLE_ENDED,
            lambda _event: call_order.append("emit"),
        )

        # Set up mock learning store whose update_zone_data records when save fires
        mock_learning_store = MagicMock()
        mock_learning_store.update_zone_data = MagicMock(side_effect=lambda **_kwargs: call_order.append("save"))
        mock_learning_store.schedule_zone_save = MagicMock()

        # Wire hass.data so _schedule_learning_save finds the store
        mock_hass.data = {DOMAIN: {"learning_store": mock_learning_store}}

        recorder = CycleMetricsRecorder(
            hass=mock_hass,
            zone_id="test_order",
            adaptive_learner=mock_adaptive_learner,
            get_target_temp=mock_callbacks["get_target_temp"],
            get_current_temp=mock_callbacks["get_current_temp"],
            get_hvac_mode=mock_callbacks["get_hvac_mode"],
            get_in_grace_period=mock_callbacks["get_in_grace_period"],
            min_cycle_duration_minutes=5,
            heating_type=HeatingType.FLOOR_HYDRONIC,
            dispatcher=dispatcher,
        )

        # Build a valid temperature history (6 samples, 25 min cycle)
        cycle_start = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        temperature_history = [(cycle_start + timedelta(minutes=i * 5), 18.0 + i * 0.4) for i in range(6)]

        # Act: record cycle metrics
        recorder.record_cycle_metrics(
            cycle_start_time=cycle_start,
            cycle_target_temp=20.0,
            cycle_state_value="settling",
            temperature_history=temperature_history,
            outdoor_temp_history=[],
        )

        # Assert ordering: emit must appear before save in the call log
        assert "emit" in call_order, "CYCLE_ENDED event was never emitted"
        assert "save" in call_order, "Learning save was never scheduled"
        emit_idx = call_order.index("emit")
        save_idx = call_order.index("save")
        assert emit_idx < save_idx, (
            f"Expected emit (idx={emit_idx}) before save (idx={save_idx}), got call order: {call_order}"
        )


class TestKeDataPersistedWithCycleSave:
    """M07: ke_data must be included in update_zone_data when saving after a cycle."""

    def _make_recorder(self, mock_hass, mock_adaptive_learner, mock_callbacks, ke_manager=None):
        """Build a CycleMetricsRecorder with an optional ke_manager."""
        return CycleMetricsRecorder(
            hass=mock_hass,
            zone_id="test_ke_persist",
            adaptive_learner=mock_adaptive_learner,
            get_target_temp=mock_callbacks["get_target_temp"],
            get_current_temp=mock_callbacks["get_current_temp"],
            get_hvac_mode=mock_callbacks["get_hvac_mode"],
            get_in_grace_period=mock_callbacks["get_in_grace_period"],
            min_cycle_duration_minutes=5,
            heating_type=HeatingType.RADIATOR,
            ke_manager=ke_manager,
        )

    def _run_one_cycle(self, recorder, mock_hass):
        """Wire a learning store and record a valid 6-sample cycle."""
        from datetime import timedelta
        from custom_components.adaptive_climate.const import DOMAIN

        mock_store = MagicMock()
        mock_store.schedule_zone_save = MagicMock()
        captured = {}
        mock_store.update_zone_data = MagicMock(side_effect=lambda **kw: captured.update(kw))
        mock_hass.data = {DOMAIN: {"learning_store": mock_store}}

        cycle_start = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        temperature_history = [(cycle_start + timedelta(minutes=i * 5), 18.0 + i * 0.4) for i in range(6)]
        recorder.record_cycle_metrics(
            cycle_start_time=cycle_start,
            cycle_target_temp=20.0,
            cycle_state_value="settling",
            temperature_history=temperature_history,
            outdoor_temp_history=[],
        )
        return captured, mock_store

    def test_ke_data_included_when_ke_manager_present(self, mock_hass, mock_adaptive_learner, mock_callbacks):
        """M07: update_zone_data must receive ke_data when ke_manager is set."""
        ke_manager = MagicMock()
        ke_manager.get_learner_dict.return_value = {"ke": 0.5, "observations": 3}

        recorder = self._make_recorder(mock_hass, mock_adaptive_learner, mock_callbacks, ke_manager)
        captured, _ = self._run_one_cycle(recorder, mock_hass)

        assert "ke_data" in captured, "ke_data key missing from update_zone_data call"
        assert captured["ke_data"] == {"ke": 0.5, "observations": 3}
        ke_manager.get_learner_dict.assert_called_once()

    def test_ke_data_none_when_no_ke_manager(self, mock_hass, mock_adaptive_learner, mock_callbacks):
        """M07: ke_data=None when no ke_manager provided (backwards-compat)."""
        recorder = self._make_recorder(mock_hass, mock_adaptive_learner, mock_callbacks, ke_manager=None)
        captured, _ = self._run_one_cycle(recorder, mock_hass)

        assert captured.get("ke_data") is None

    def test_ke_data_none_when_learner_dict_returns_none(self, mock_hass, mock_adaptive_learner, mock_callbacks):
        """M07: ke_data=None when get_learner_dict() returns None (no KeLearner)."""
        ke_manager = MagicMock()
        ke_manager.get_learner_dict.return_value = None

        recorder = self._make_recorder(mock_hass, mock_adaptive_learner, mock_callbacks, ke_manager)
        captured, _ = self._run_one_cycle(recorder, mock_hass)

        assert captured.get("ke_data") is None


class TestKeManagerGetLearnerDict:
    """M07: KeManager.get_learner_dict() must delegate to KeLearner.to_dict()."""

    def test_returns_learner_to_dict_when_present(self):
        """get_learner_dict() returns KeLearner.to_dict() result."""
        from custom_components.adaptive_climate.managers.ke_manager import KeManager

        ke_manager = MagicMock(spec=KeManager)
        ke_manager.get_learner_dict = KeManager.get_learner_dict.__get__(ke_manager)

        mock_learner = MagicMock()
        mock_learner.to_dict.return_value = {"ke": 0.4, "n": 5}
        ke_manager._ke_learner = mock_learner

        result = ke_manager.get_learner_dict()
        assert result == {"ke": 0.4, "n": 5}
        mock_learner.to_dict.assert_called_once()

    def test_returns_none_when_no_learner(self):
        """get_learner_dict() returns None when _ke_learner is None."""
        from custom_components.adaptive_climate.managers.ke_manager import KeManager

        ke_manager = MagicMock(spec=KeManager)
        ke_manager.get_learner_dict = KeManager.get_learner_dict.__get__(ke_manager)
        ke_manager._ke_learner = None

        result = ke_manager.get_learner_dict()
        assert result is None
