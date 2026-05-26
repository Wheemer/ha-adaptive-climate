"""Unit tests for PauseDetector."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

from custom_components.adaptive_climate.managers.pause_detector import PauseDetector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _contact(*, any_open: bool = False, should_take_action: bool = False, action_is_pause: bool = True):
    """Return a mock ContactSensorHandler."""
    from custom_components.adaptive_climate.adaptive.contact_sensors import ContactAction

    handler = MagicMock()
    handler.is_any_contact_open.return_value = any_open
    handler.should_take_action.return_value = should_take_action
    handler.get_action.return_value = ContactAction.PAUSE if action_is_pause else ContactAction.FROST_PROTECTION
    return handler


def _humidity(*, paused: bool = False):
    """Return a mock HumidityDetector."""
    detector = MagicMock()
    detector.should_pause.return_value = paused
    return detector


def _night_setback(*, in_grace: bool = False):
    """Return a mock NightSetbackManager with in_learning_grace_period property."""
    controller = MagicMock()
    type(controller).in_learning_grace_period = PropertyMock(return_value=in_grace)
    return controller


# ---------------------------------------------------------------------------
# is_learning_paused – all None handlers
# ---------------------------------------------------------------------------


class TestIsLearningPausedNoHandlers:
    """is_learning_paused returns False when no handlers are configured."""

    def test_all_none_returns_false(self):
        detector = PauseDetector()
        assert detector.is_learning_paused() is False

    def test_only_night_setback_none(self):
        detector = PauseDetector(
            contact_sensor_handler=_contact(any_open=False),
            humidity_detector=_humidity(paused=False),
        )
        assert detector.is_learning_paused() is False


# ---------------------------------------------------------------------------
# is_learning_paused – individual conditions
# ---------------------------------------------------------------------------


class TestIsLearningPausedConditions:
    """Each condition independently triggers is_learning_paused."""

    def test_learning_grace_triggers_pause(self):
        detector = PauseDetector(night_setback_controller=_night_setback(in_grace=True))
        assert detector.is_learning_paused() is True

    def test_learning_grace_false_does_not_pause(self):
        detector = PauseDetector(night_setback_controller=_night_setback(in_grace=False))
        assert detector.is_learning_paused() is False

    def test_contact_open_triggers_pause(self):
        detector = PauseDetector(contact_sensor_handler=_contact(any_open=True))
        assert detector.is_learning_paused() is True

    def test_contact_closed_does_not_pause(self):
        detector = PauseDetector(contact_sensor_handler=_contact(any_open=False))
        assert detector.is_learning_paused() is False

    def test_humidity_spike_triggers_pause(self):
        detector = PauseDetector(humidity_detector=_humidity(paused=True))
        assert detector.is_learning_paused() is True

    def test_humidity_normal_does_not_pause(self):
        detector = PauseDetector(humidity_detector=_humidity(paused=False))
        assert detector.is_learning_paused() is False


# ---------------------------------------------------------------------------
# is_learning_paused – priority ordering (short-circuit)
# ---------------------------------------------------------------------------


class TestIsLearningPausedPriority:
    """Learning grace is checked first; contact before humidity."""

    def test_grace_checked_before_contact(self):
        """Grace period active → returns True without consulting contact."""
        contact = _contact(any_open=False)
        detector = PauseDetector(
            night_setback_controller=_night_setback(in_grace=True),
            contact_sensor_handler=contact,
        )
        assert detector.is_learning_paused() is True
        contact.is_any_contact_open.assert_not_called()

    def test_contact_checked_before_humidity(self):
        """Contact open → returns True without consulting humidity."""
        hum = _humidity(paused=False)
        detector = PauseDetector(
            contact_sensor_handler=_contact(any_open=True),
            humidity_detector=hum,
        )
        assert detector.is_learning_paused() is True
        hum.should_pause.assert_not_called()

    def test_all_three_active_returns_true(self):
        detector = PauseDetector(
            night_setback_controller=_night_setback(in_grace=True),
            contact_sensor_handler=_contact(any_open=True),
            humidity_detector=_humidity(paused=True),
        )
        assert detector.is_learning_paused() is True


# ---------------------------------------------------------------------------
# is_learning_paused – exception tolerance
# ---------------------------------------------------------------------------


class TestIsLearningPausedExceptions:
    """Exceptions from handlers are swallowed and treated as not-paused."""

    def test_grace_property_raises_attribute_error(self):
        # PropertyMock(side_effect=AttributeError) is unreliable: Python's
        # descriptor protocol catches AttributeError from __get__ and falls back
        # to MagicMock.__getattr__, which returns a truthy Mock.  Use a real
        # class so the exception propagates correctly to our try/except block.
        class FailingGrace:
            @property
            def in_learning_grace_period(self) -> bool:
                raise AttributeError("simulated HA boundary error")

        detector = PauseDetector(night_setback_controller=FailingGrace())  # type: ignore[arg-type]
        assert detector.is_learning_paused() is False

    def test_contact_raises_type_error(self):
        contact = MagicMock()
        contact.is_any_contact_open.side_effect = TypeError
        detector = PauseDetector(contact_sensor_handler=contact)
        assert detector.is_learning_paused() is False

    def test_humidity_raises_attribute_error(self):
        hum = MagicMock()
        hum.should_pause.side_effect = AttributeError
        detector = PauseDetector(humidity_detector=hum)
        assert detector.is_learning_paused() is False


# ---------------------------------------------------------------------------
# is_control_paused – basic cases
# ---------------------------------------------------------------------------


class TestIsControlPaused:
    """is_control_paused uses delay-aware contact check and ignores grace."""

    def test_no_handlers_returns_false(self):
        detector = PauseDetector()
        assert detector.is_control_paused() is False

    def test_contact_not_taking_action_returns_false(self):
        detector = PauseDetector(contact_sensor_handler=_contact(should_take_action=False))
        assert detector.is_control_paused() is False

    def test_contact_taking_action_with_pause_action_returns_true(self):
        detector = PauseDetector(contact_sensor_handler=_contact(should_take_action=True, action_is_pause=True))
        assert detector.is_control_paused() is True

    def test_contact_taking_action_with_frost_action_returns_false(self):
        """FROST_PROTECTION action should not trigger a control pause."""
        detector = PauseDetector(contact_sensor_handler=_contact(should_take_action=True, action_is_pause=False))
        assert detector.is_control_paused() is False

    def test_humidity_spike_triggers_control_pause(self):
        detector = PauseDetector(humidity_detector=_humidity(paused=True))
        assert detector.is_control_paused() is True

    def test_learning_grace_does_not_affect_control_pause(self):
        """Grace period is irrelevant for actuator pause decisions."""
        detector = PauseDetector(
            night_setback_controller=_night_setback(in_grace=True),
            contact_sensor_handler=_contact(should_take_action=False),
            humidity_detector=_humidity(paused=False),
        )
        assert detector.is_control_paused() is False

    def test_hvac_mode_passed_to_get_action(self):
        contact = _contact(should_take_action=True, action_is_pause=True)
        detector = PauseDetector(contact_sensor_handler=contact)
        detector.is_control_paused(hvac_mode="heat")
        contact.get_action.assert_called_once_with("heat")

    def test_contact_exception_is_swallowed(self):
        contact = MagicMock()
        contact.should_take_action.side_effect = TypeError
        detector = PauseDetector(contact_sensor_handler=contact)
        assert detector.is_control_paused() is False


# ---------------------------------------------------------------------------
# from_entity classmethod
# ---------------------------------------------------------------------------


class TestFromEntity:
    """from_entity extracts component references safely from any object."""

    def test_fully_equipped_entity(self):
        """All three attributes present and set."""
        entity = MagicMock()
        entity._night_setback_controller = _night_setback(in_grace=True)
        entity._contact_sensor_handler = _contact(any_open=False)
        entity._humidity_detector = _humidity(paused=False)

        detector = PauseDetector.from_entity(entity)
        assert detector._night_setback_controller is entity._night_setback_controller
        assert detector._contact_sensor_handler is entity._contact_sensor_handler
        assert detector._humidity_detector is entity._humidity_detector

    def test_entity_missing_all_attributes(self):
        """Object with no climate attributes returns safe no-pause detector."""

        class Bare:
            pass

        detector = PauseDetector.from_entity(Bare())
        assert detector._night_setback_controller is None
        assert detector._contact_sensor_handler is None
        assert detector._humidity_detector is None
        assert detector.is_learning_paused() is False

    def test_entity_with_none_controllers(self):
        """Attributes present but set to None behave like missing."""
        entity = MagicMock()
        entity._night_setback_controller = None
        entity._contact_sensor_handler = None
        entity._humidity_detector = None

        detector = PauseDetector.from_entity(entity)
        assert detector.is_learning_paused() is False

    def test_from_entity_grace_active(self):
        """End-to-end: entity with grace active → is_learning_paused True."""
        entity = MagicMock()
        entity._night_setback_controller = _night_setback(in_grace=True)
        entity._contact_sensor_handler = None
        entity._humidity_detector = None

        assert PauseDetector.from_entity(entity).is_learning_paused() is True

    def test_from_entity_contact_open(self):
        """End-to-end: entity with contact open → is_learning_paused True."""
        entity = MagicMock()
        entity._night_setback_controller = None
        entity._contact_sensor_handler = _contact(any_open=True)
        entity._humidity_detector = None

        assert PauseDetector.from_entity(entity).is_learning_paused() is True

    def test_from_entity_humidity_spike(self):
        """End-to-end: entity with humidity spike → is_learning_paused True."""
        entity = MagicMock()
        entity._night_setback_controller = None
        entity._contact_sensor_handler = None
        entity._humidity_detector = _humidity(paused=True)

        assert PauseDetector.from_entity(entity).is_learning_paused() is True
