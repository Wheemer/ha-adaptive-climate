"""Tests for contact sensor module."""

import pytest
from datetime import datetime, timedelta
from custom_components.adaptive_climate.adaptive.contact_sensors import (
    ContactSensorHandler,
    ContactSensorManager,
    ContactAction,
)


class TestContactSensorHandler:
    """Test ContactSensorHandler class."""

    def test_contact_delay(self):
        """Test that action is delayed after contact opens."""
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window_bedroom"],
            contact_delay_seconds=300,  # 5 minutes
        )

        current_time = datetime(2024, 1, 15, 10, 0)

        # Update state: window opens
        handler.update_contact_states({"binary_sensor.window_bedroom": True}, current_time)

        # Immediately after opening - no action yet
        assert handler.should_take_action(current_time) is False
        assert handler.is_any_contact_open() is True

        # 2 minutes later - still no action
        time_2min = current_time + timedelta(minutes=2)
        assert handler.should_take_action(time_2min) is False

        # 5 minutes later - action should be taken
        time_5min = current_time + timedelta(minutes=5)
        assert handler.should_take_action(time_5min) is True

        # 10 minutes later - action should still be taken
        time_10min = current_time + timedelta(minutes=10)
        assert handler.should_take_action(time_10min) is True

    def test_pause_action(self):
        """Test pause action stops heating."""
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window_bedroom"],
            contact_delay_seconds=0,  # No delay for testing
            action=ContactAction.PAUSE,
        )

        current_time = datetime(2024, 1, 15, 10, 0)
        base_setpoint = 20.0

        # Window closed - no adjustment
        handler.update_contact_states({"binary_sensor.window_bedroom": False}, current_time)
        assert handler.get_adjusted_setpoint(base_setpoint, current_time) is None

        # Window opens - pause heating (returns None)
        handler.update_contact_states({"binary_sensor.window_bedroom": True}, current_time)
        adjusted = handler.get_adjusted_setpoint(base_setpoint, current_time)
        assert adjusted is None  # None indicates pause
        assert handler.get_action() == ContactAction.PAUSE

    def test_frost_protection_action(self):
        """Test frost protection action lowers temperature."""
        frost_temp = 5.0
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.door_bathroom"],
            contact_delay_seconds=0,  # No delay for testing
            action=ContactAction.FROST_PROTECTION,
            frost_protection_temp=frost_temp,
        )

        current_time = datetime(2024, 1, 15, 10, 0)
        base_setpoint = 20.0

        # Door closed - no adjustment
        handler.update_contact_states({"binary_sensor.door_bathroom": False}, current_time)
        assert handler.get_adjusted_setpoint(base_setpoint, current_time) is None

        # Door opens - frost protection
        handler.update_contact_states({"binary_sensor.door_bathroom": True}, current_time)
        adjusted = handler.get_adjusted_setpoint(base_setpoint, current_time)
        assert adjusted == frost_temp
        assert handler.get_action() == ContactAction.FROST_PROTECTION

    def test_grace_period(self):
        """Test learning grace period prevents action."""
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window_living_room"],
            contact_delay_seconds=0,  # No contact delay
            learning_grace_seconds=3600,  # 1 hour grace period
        )

        current_time = datetime(2024, 1, 15, 10, 0)

        # Window opens immediately
        handler.update_contact_states({"binary_sensor.window_living_room": True}, current_time)

        # During grace period - no action
        assert handler.should_take_action(current_time) is False
        assert handler.get_grace_time_remaining(current_time) == 3600

        # 30 minutes later - still in grace period
        time_30min = current_time + timedelta(minutes=30)
        assert handler.should_take_action(time_30min) is False
        assert handler.get_grace_time_remaining(time_30min) == 1800

        # 1 hour later - grace period expired, action taken
        time_1hour = current_time + timedelta(hours=1)
        assert handler.should_take_action(time_1hour) is True
        assert handler.get_grace_time_remaining(time_1hour) == 0

    def test_multi_sensor_aggregation(self):
        """Test aggregation of multiple contact sensors."""
        handler = ContactSensorHandler(
            contact_sensors=[
                "binary_sensor.window_bedroom_1",
                "binary_sensor.window_bedroom_2",
                "binary_sensor.door_bedroom",
            ],
            contact_delay_seconds=0,  # No delay for testing
        )

        current_time = datetime(2024, 1, 15, 10, 0)

        # All closed - no action
        handler.update_contact_states(
            {
                "binary_sensor.window_bedroom_1": False,
                "binary_sensor.window_bedroom_2": False,
                "binary_sensor.door_bedroom": False,
            },
            current_time,
        )
        assert handler.is_any_contact_open() is False
        assert handler.should_take_action(current_time) is False

        # One window opens - action taken (ANY open triggers)
        handler.update_contact_states(
            {
                "binary_sensor.window_bedroom_1": True,
                "binary_sensor.window_bedroom_2": False,
                "binary_sensor.door_bedroom": False,
            },
            current_time,
        )
        assert handler.is_any_contact_open() is True
        assert handler.should_take_action(current_time) is True

        # Multiple open - still triggers action
        handler.update_contact_states(
            {
                "binary_sensor.window_bedroom_1": True,
                "binary_sensor.window_bedroom_2": True,
                "binary_sensor.door_bedroom": False,
            },
            current_time,
        )
        assert handler.is_any_contact_open() is True
        assert handler.should_take_action(current_time) is True

        # All closed again - no action
        handler.update_contact_states(
            {
                "binary_sensor.window_bedroom_1": False,
                "binary_sensor.window_bedroom_2": False,
                "binary_sensor.door_bedroom": False,
            },
            current_time,
        )
        assert handler.is_any_contact_open() is False
        assert handler.should_take_action(current_time) is False

    def test_time_until_action(self):
        """Test getting time remaining until action."""
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window_kitchen"],
            contact_delay_seconds=600,  # 10 minutes
        )

        current_time = datetime(2024, 1, 15, 10, 0)

        # No contact open - no action pending
        handler.update_contact_states({"binary_sensor.window_kitchen": False}, current_time)
        assert handler.get_time_until_action(current_time) is None

        # Contact opens
        handler.update_contact_states({"binary_sensor.window_kitchen": True}, current_time)

        # Immediately - 600 seconds until action
        assert handler.get_time_until_action(current_time) == 600

        # 5 minutes later - 300 seconds remaining
        time_5min = current_time + timedelta(minutes=5)
        assert handler.get_time_until_action(time_5min) == 300

        # 10 minutes later - action should happen now
        time_10min = current_time + timedelta(minutes=10)
        assert handler.get_time_until_action(time_10min) == 0

    def test_contact_state_transitions(self):
        """Test contact open/close transitions are tracked correctly."""
        handler = ContactSensorHandler(contact_sensors=["binary_sensor.window_study"], contact_delay_seconds=300)

        current_time = datetime(2024, 1, 15, 10, 0)

        # Initial state - closed
        assert handler.is_any_contact_open() is False

        # Opens
        handler.update_contact_states({"binary_sensor.window_study": True}, current_time)
        assert handler.is_any_contact_open() is True

        # Wait for delay
        time_after_delay = current_time + timedelta(minutes=5)
        assert handler.should_take_action(time_after_delay) is True

        # Closes - should reset
        handler.update_contact_states({"binary_sensor.window_study": False}, current_time)
        assert handler.is_any_contact_open() is False
        assert handler.should_take_action(time_after_delay) is False


class TestContactSensorManager:
    """Test ContactSensorManager class."""

    def test_configure_zone(self):
        """Test zone configuration."""
        manager = ContactSensorManager()

        manager.configure_zone(
            zone_id="bedroom",
            contact_sensors=["binary_sensor.window_bedroom"],
            contact_delay_seconds=300,
            action="pause",
        )

        config = manager.get_zone_config("bedroom")
        assert config is not None
        assert config["contact_sensors"] == ["binary_sensor.window_bedroom"]
        assert config["contact_delay_seconds"] == 300
        assert config["action"] == "pause"

    def test_should_take_action_for_zone(self):
        """Test checking if zone should take action."""
        manager = ContactSensorManager()

        manager.configure_zone(
            zone_id="kitchen", contact_sensors=["binary_sensor.window_kitchen"], contact_delay_seconds=0
        )

        current_time = datetime(2024, 1, 15, 10, 0)

        # Contact closed - no action
        manager.update_contact_states("kitchen", {"binary_sensor.window_kitchen": False}, current_time)
        assert manager.should_take_action("kitchen", current_time) is False

        # Contact opens - action
        manager.update_contact_states("kitchen", {"binary_sensor.window_kitchen": True}, current_time)
        assert manager.should_take_action("kitchen", current_time) is True

    def test_get_adjusted_setpoint_for_zone(self):
        """Test getting adjusted setpoint for a zone."""
        manager = ContactSensorManager()

        manager.configure_zone(
            zone_id="bathroom",
            contact_sensors=["binary_sensor.window_bathroom"],
            contact_delay_seconds=0,
            action="frost_protection",
            frost_protection_temp=7.0,
        )

        current_time = datetime(2024, 1, 15, 10, 0)
        base_setpoint = 22.0

        # Contact closed - no adjustment
        manager.update_contact_states("bathroom", {"binary_sensor.window_bathroom": False}, current_time)
        adjusted = manager.get_adjusted_setpoint("bathroom", base_setpoint, current_time)
        assert adjusted is None

        # Contact opens - frost protection
        manager.update_contact_states("bathroom", {"binary_sensor.window_bathroom": True}, current_time)
        adjusted = manager.get_adjusted_setpoint("bathroom", base_setpoint, current_time)
        assert adjusted == 7.0

    def test_unconfigured_zone_returns_none(self):
        """Test that unconfigured zones return None."""
        manager = ContactSensorManager()

        assert manager.get_zone_config("nonexistent") is None
        assert manager.should_take_action("nonexistent") is False
        assert manager.get_adjusted_setpoint("nonexistent", 20.0) is None

    def test_multiple_zones_independence(self):
        """Test that multiple zones operate independently."""
        manager = ContactSensorManager()

        # Configure two zones
        manager.configure_zone(
            zone_id="bedroom", contact_sensors=["binary_sensor.window_bedroom"], contact_delay_seconds=0, action="pause"
        )

        manager.configure_zone(
            zone_id="living_room",
            contact_sensors=["binary_sensor.window_living_room"],
            contact_delay_seconds=0,
            action="frost_protection",
            frost_protection_temp=5.0,
        )

        current_time = datetime(2024, 1, 15, 10, 0)

        # Open bedroom window only
        manager.update_contact_states("bedroom", {"binary_sensor.window_bedroom": True}, current_time)
        manager.update_contact_states("living_room", {"binary_sensor.window_living_room": False}, current_time)

        # Bedroom should take action, living room should not
        assert manager.should_take_action("bedroom", current_time) is True
        assert manager.should_take_action("living_room", current_time) is False

        # Verify different actions
        bedroom_handler = manager.get_handler("bedroom")
        living_room_handler = manager.get_handler("living_room")
        assert bedroom_handler.get_action() == ContactAction.PAUSE
        assert living_room_handler.get_action() == ContactAction.FROST_PROTECTION


class TestContactAccumulatorReset:
    """Tests for duty accumulator reset respecting contact_delay (Story 3.3).

    The accumulator must NOT be reset immediately when a contact sensor opens.
    It should only be reset when the pause actually begins (after contact_delay elapses)
    and only on the first control loop iteration that detects the paused state.
    """

    def _make_control_loop_check(self, handler: ContactSensorHandler, mock_heater_controller):
        """Build a minimal object that mirrors the transition-detection logic in
        _async_control_heating.  Returns a callable that simulates one control loop
        iteration, advancing time as requested.
        """
        from unittest.mock import MagicMock

        class ControlLoopSimulator:
            def __init__(self):
                self._contact_sensor_handler = handler
                self._heater_controller = mock_heater_controller
                self._contact_was_paused = False

            def tick(self, current_time: datetime) -> bool:
                """Simulate one iteration.  Returns True when the accumulator was reset."""
                contact_paused_now = self._contact_sensor_handler.should_take_action(current_time)
                reset_happened = False
                if contact_paused_now and not self._contact_was_paused:
                    if self._heater_controller is not None:
                        self._heater_controller.reset_duty_accumulator()
                        reset_happened = True
                self._contact_was_paused = contact_paused_now if contact_paused_now else False
                if not contact_paused_now:
                    self._contact_was_paused = False
                return reset_happened

        return ControlLoopSimulator()

    def test_accumulator_not_reset_immediately_on_open(self):
        """Accumulator must NOT be reset the moment a contact sensor opens."""
        from unittest.mock import MagicMock

        mock_heater_controller = MagicMock()
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window_bedroom"],
            contact_delay_seconds=300,  # 5-minute delay
        )
        sim = self._make_control_loop_check(handler, mock_heater_controller)

        t0 = datetime(2024, 1, 15, 10, 0)
        handler.update_contact_states({"binary_sensor.window_bedroom": True}, t0)

        # Control loop runs immediately after open — delay not elapsed yet
        reset = sim.tick(t0)

        assert reset is False
        mock_heater_controller.reset_duty_accumulator.assert_not_called()

    def test_accumulator_reset_when_pause_begins(self):
        """Accumulator IS reset on the first control loop tick after delay elapses."""
        from unittest.mock import MagicMock

        mock_heater_controller = MagicMock()
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window_bedroom"],
            contact_delay_seconds=300,
        )
        sim = self._make_control_loop_check(handler, mock_heater_controller)

        t0 = datetime(2024, 1, 15, 10, 0)
        handler.update_contact_states({"binary_sensor.window_bedroom": True}, t0)

        # Tick before delay — no reset
        sim.tick(t0)
        mock_heater_controller.reset_duty_accumulator.assert_not_called()

        # Tick after delay elapses — first pause iteration → accumulator reset
        t_after = t0 + timedelta(minutes=5)
        reset = sim.tick(t_after)

        assert reset is True
        mock_heater_controller.reset_duty_accumulator.assert_called_once()

    def test_accumulator_reset_only_once_per_pause(self):
        """Accumulator is reset exactly once per contact-open event, not on every tick."""
        from unittest.mock import MagicMock

        mock_heater_controller = MagicMock()
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window_bedroom"],
            contact_delay_seconds=0,  # No delay for simplicity
        )
        sim = self._make_control_loop_check(handler, mock_heater_controller)

        t0 = datetime(2024, 1, 15, 10, 0)
        handler.update_contact_states({"binary_sensor.window_bedroom": True}, t0)

        # Three consecutive ticks while contact remains open
        sim.tick(t0)
        sim.tick(t0 + timedelta(minutes=1))
        sim.tick(t0 + timedelta(minutes=2))

        # Should have been called exactly once (the first tick after open)
        assert mock_heater_controller.reset_duty_accumulator.call_count == 1

    def test_accumulator_reset_again_on_reopen(self):
        """After close → reopen, the accumulator is reset again on the next pause."""
        from unittest.mock import MagicMock

        mock_heater_controller = MagicMock()
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window_bedroom"],
            contact_delay_seconds=0,
        )
        sim = self._make_control_loop_check(handler, mock_heater_controller)

        t0 = datetime(2024, 1, 15, 10, 0)

        # First open — pause begins — accumulator reset
        handler.update_contact_states({"binary_sensor.window_bedroom": True}, t0)
        sim.tick(t0)
        assert mock_heater_controller.reset_duty_accumulator.call_count == 1

        # Close — no pause
        handler.update_contact_states({"binary_sensor.window_bedroom": False}, t0 + timedelta(minutes=10))
        sim.tick(t0 + timedelta(minutes=10))
        assert mock_heater_controller.reset_duty_accumulator.call_count == 1

        # Reopen — pause begins again — accumulator reset a second time
        handler.update_contact_states({"binary_sensor.window_bedroom": True}, t0 + timedelta(minutes=20))
        sim.tick(t0 + timedelta(minutes=20))
        assert mock_heater_controller.reset_duty_accumulator.call_count == 2

    def test_contact_close_does_not_reset_accumulator(self):
        """Closing a contact sensor does NOT reset the duty accumulator."""
        from unittest.mock import MagicMock

        mock_heater_controller = MagicMock()
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window_bedroom"],
            contact_delay_seconds=0,
        )
        sim = self._make_control_loop_check(handler, mock_heater_controller)

        t0 = datetime(2024, 1, 15, 10, 0)

        # Open then pause is detected
        handler.update_contact_states({"binary_sensor.window_bedroom": True}, t0)
        sim.tick(t0)
        mock_heater_controller.reset_duty_accumulator.reset_mock()

        # Close — tick — no further reset
        handler.update_contact_states({"binary_sensor.window_bedroom": False}, t0 + timedelta(minutes=5))
        sim.tick(t0 + timedelta(minutes=5))

        mock_heater_controller.reset_duty_accumulator.assert_not_called()


class TestContactActionNone:
    """M05: contact_action=none must never pause heating or learning."""

    def test_none_action_does_not_pause_control(self):
        """M05: is_control_paused() must return False when action is NONE and sensor is open.

        Bug: climate.py maps contact_action='none' to ContactAction.FROST_PROTECTION
        (binary else branch), so the zone gets a frost-protection setpoint instead of
        no action at all.

        Fix (step 1): add ContactAction.NONE to the enum so it can be expressed.
        Fix (step 2): climate.py maps 'none' -> ContactAction.NONE.
        PauseDetector.is_control_paused() already works because it checks
        ``get_action() == PAUSE``; NONE != PAUSE so no pause fires.
        """
        from custom_components.adaptive_climate.managers.pause_detector import PauseDetector

        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window"],
            contact_delay_seconds=0,  # no delay — action fires immediately
            action=ContactAction.NONE,
        )
        t0 = datetime(2024, 1, 1, 10, 0)
        handler.update_contact_states({"binary_sensor.window": True}, t0)

        pause_detector = PauseDetector(contact_sensor_handler=handler)

        assert not pause_detector.is_control_paused("heat"), (
            "M05: contact_action=none must not pause heating control "
            "even when the sensor is open and the delay has elapsed."
        )

    def test_none_action_does_not_pause_learning(self):
        """M05: is_learning_paused() must return False when action is NONE and sensor is open.

        Bug: PauseDetector.is_learning_paused() calls is_any_contact_open() directly,
        without checking whether the configured action is NONE (observe-only).  When
        a sensor is open with action=NONE, learning is incorrectly paused.

        Fix: is_learning_paused() must skip the pause check when handler.action == NONE.
        """
        from custom_components.adaptive_climate.managers.pause_detector import PauseDetector

        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window"],
            contact_delay_seconds=0,
            action=ContactAction.NONE,
        )
        t0 = datetime(2024, 1, 1, 10, 0)
        handler.update_contact_states({"binary_sensor.window": True}, t0)

        pause_detector = PauseDetector(contact_sensor_handler=handler)

        assert not pause_detector.is_learning_paused(), (
            "M05: contact_action=none must not pause learning analysis "
            "when a sensor is open — NONE is observe-only, not a pause trigger."
        )

    def test_none_action_does_not_adjust_setpoint(self):
        """M05: get_adjusted_setpoint() must return None (no change) for action=NONE."""
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window"],
            contact_delay_seconds=0,
            action=ContactAction.NONE,
        )
        t0 = datetime(2024, 1, 1, 10, 0)
        handler.update_contact_states({"binary_sensor.window": True}, t0)

        result = handler.get_adjusted_setpoint(base_setpoint=20.0, current_time=t0)

        assert result is None, f"M05: contact_action=none must not adjust setpoint, got {result!r}."


class TestContactActionClamp:
    """Tests for contact_action=clamp which offsets setpoint by 2°C."""

    def test_clamp_action_lowers_setpoint_in_heat_mode(self):
        """CLAMP action lowers setpoint by 2°C when heating."""
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window"],
            contact_delay_seconds=0,
            action=ContactAction.CLAMP,
        )
        t0 = datetime(2024, 1, 1, 10, 0)
        handler.update_contact_states({"binary_sensor.window": True}, t0)

        result = handler.get_adjusted_setpoint(base_setpoint=20.0, current_time=t0, hvac_mode="heat")

        assert result == 18.0, f"CLAMP in heat mode should lower setpoint by 2°C, got {result}"

    def test_clamp_action_raises_setpoint_in_cool_mode(self):
        """CLAMP action raises setpoint by 2°C when cooling."""
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window"],
            contact_delay_seconds=0,
            action=ContactAction.CLAMP,
        )
        t0 = datetime(2024, 1, 1, 10, 0)
        handler.update_contact_states({"binary_sensor.window": True}, t0)

        result = handler.get_adjusted_setpoint(base_setpoint=24.0, current_time=t0, hvac_mode="cool")

        assert result == 26.0, f"CLAMP in cool mode should raise setpoint by 2°C, got {result}"

    def test_clamp_action_defaults_to_heat_when_mode_unknown(self):
        """CLAMP action defaults to lowering setpoint when hvac_mode is None."""
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window"],
            contact_delay_seconds=0,
            action=ContactAction.CLAMP,
        )
        t0 = datetime(2024, 1, 1, 10, 0)
        handler.update_contact_states({"binary_sensor.window": True}, t0)

        result = handler.get_adjusted_setpoint(base_setpoint=20.0, current_time=t0, hvac_mode=None)

        assert result == 18.0, f"CLAMP with no mode should lower setpoint, got {result}"

    def test_clamp_action_does_not_pause_control(self):
        """CLAMP action does NOT trigger a control pause."""
        from custom_components.adaptive_climate.managers.pause_detector import PauseDetector

        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window"],
            contact_delay_seconds=0,
            action=ContactAction.CLAMP,
        )
        t0 = datetime(2024, 1, 1, 10, 0)
        handler.update_contact_states({"binary_sensor.window": True}, t0)

        pause_detector = PauseDetector(contact_sensor_handler=handler)

        assert not pause_detector.is_control_paused("heat"), (
            "CLAMP must not pause heating control — it adjusts setpoint instead"
        )
        assert not pause_detector.is_control_paused("cool"), (
            "CLAMP must not pause cooling control — it adjusts setpoint instead"
        )

    def test_clamp_action_pauses_learning(self):
        """CLAMP action DOES pause learning (any setpoint adjustment invalidates cycles)."""
        from custom_components.adaptive_climate.managers.pause_detector import PauseDetector

        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window"],
            contact_delay_seconds=0,
            action=ContactAction.CLAMP,
        )
        t0 = datetime(2024, 1, 1, 10, 0)
        handler.update_contact_states({"binary_sensor.window": True}, t0)

        pause_detector = PauseDetector(contact_sensor_handler=handler)

        assert pause_detector.is_learning_paused(), "CLAMP should pause learning when contact is open"

    def test_clamp_no_adjustment_when_closed(self):
        """CLAMP returns None (no adjustment) when contact is closed."""
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window"],
            contact_delay_seconds=0,
            action=ContactAction.CLAMP,
        )
        t0 = datetime(2024, 1, 1, 10, 0)
        handler.update_contact_states({"binary_sensor.window": False}, t0)

        result = handler.get_adjusted_setpoint(base_setpoint=20.0, current_time=t0, hvac_mode="heat")

        assert result is None, f"CLAMP with closed contact should return None, got {result}"

    def test_clamp_respects_delay(self):
        """CLAMP respects contact_delay before adjusting setpoint."""
        handler = ContactSensorHandler(
            contact_sensors=["binary_sensor.window"],
            contact_delay_seconds=300,  # 5 minutes
            action=ContactAction.CLAMP,
        )
        t0 = datetime(2024, 1, 1, 10, 0)
        handler.update_contact_states({"binary_sensor.window": True}, t0)

        # Before delay
        result = handler.get_adjusted_setpoint(base_setpoint=20.0, current_time=t0, hvac_mode="heat")
        assert result is None, "CLAMP should not adjust before delay expires"

        # After delay
        t5 = t0 + timedelta(minutes=5)
        result = handler.get_adjusted_setpoint(base_setpoint=20.0, current_time=t5, hvac_mode="heat")
        assert result == 18.0, f"CLAMP should adjust after delay, got {result}"

    def test_manager_configures_clamp_action(self):
        """ContactSensorManager correctly maps 'clamp' string to ContactAction.CLAMP."""
        manager = ContactSensorManager()
        manager.configure_zone(
            zone_id="bedroom",
            contact_sensors=["binary_sensor.window"],
            contact_delay_seconds=0,
            action="clamp",
        )

        handler = manager.get_handler("bedroom")
        assert handler is not None
        assert handler.action == ContactAction.CLAMP
