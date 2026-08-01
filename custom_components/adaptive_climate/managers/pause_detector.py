"""Pause detection helper for Adaptive Climate.

Provides a single source of truth for checking whether learning analysis or
heating/cooling control should be paused, based on three conditions:

  1. Learning grace period  (night-setback controller)
  2. Any contact sensor open
  3. Humidity spike active

Two flavours are provided:

* ``is_learning_paused()`` – used when deciding whether to record/analyse
  learning cycles.  Checks grace + any-contact-open + humidity.

* ``is_control_paused(hvac_mode)`` – used when deciding whether to stop the
  heater/cooler.  Contact check is delay-aware and mode-sensitive; learning
  grace is *not* considered (it adjusts the setpoint instead of pausing the
  actuator).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..adaptive.contact_sensors import ContactSensorHandler
    from ..adaptive.humidity_detector import HumidityDetector
    from .night_setback_manager import NightSetbackManager


class PauseDetector:
    """Unified helper that detects pause conditions from injected components.

    All three component references are optional so the detector is safe to
    create even when a zone has not been fully initialised.
    """

    def __init__(
        self,
        night_setback_controller: NightSetbackManager | None = None,
        contact_sensor_handler: ContactSensorHandler | None = None,
        humidity_detector: HumidityDetector | None = None,
        water_temp_gate: bool = False,
    ) -> None:
        """Initialise with optional component references.

        Args:
            night_setback_controller: Checked for ``in_learning_grace_period``
                property when evaluating learning pauses.
            contact_sensor_handler: Checked for open contacts (learning) or
                delayed contact actions (control).
            humidity_detector: Checked via ``should_pause()`` for both flavours.
            water_temp_gate: True while the water-temperature controller is
                ramping or settling after a large write.  Suppresses learning
                only — the actuator keeps running.
        """
        self._night_setback_controller = night_setback_controller
        self._contact_sensor_handler = contact_sensor_handler
        self._humidity_detector = humidity_detector
        self._water_temp_gate = water_temp_gate

    @classmethod
    def from_entity(cls, entity: Any) -> PauseDetector:
        """Create a PauseDetector from a thermostat-like entity.

        Uses ``getattr`` with ``None`` defaults so it is safe to call with
        partially-initialised entities (e.g. during service handler scheduling).

        Args:
            entity: Any object that may expose ``_night_setback_controller``,
                ``_contact_sensor_handler``, ``_humidity_detector``, and/or
                ``water_temp_learning_gate_active``.

        Returns:
            A fully constructed :class:`PauseDetector` instance.
        """
        return cls(
            night_setback_controller=getattr(entity, "_night_setback_controller", None),
            contact_sensor_handler=getattr(entity, "_contact_sensor_handler", None),
            humidity_detector=getattr(entity, "_humidity_detector", None),
            water_temp_gate=bool(getattr(entity, "water_temp_learning_gate_active", False)),
        )

    # ------------------------------------------------------------------
    # Learning pause – used for deciding whether to analyse/record cycles
    # ------------------------------------------------------------------

    def is_learning_paused(self) -> bool:
        """Return True if learning analysis should be paused.

        Checks (in priority order):
        1. Night-setback learning grace period is active.
        2. Any contact sensor is currently open.
        3. Humidity spike (shower steam) is active.
        4. Water temperature ramp / post-write settling window is active.

        Returns:
            True if *any* pause condition is active; False otherwise.
        """
        # 1. Learning grace period
        if self._night_setback_controller is not None:
            try:
                if self._night_setback_controller.in_learning_grace_period:
                    return True
            except (TypeError, AttributeError):
                pass

        # 2. Any contact sensor open — but only when action is not NONE (observe-only)
        if self._contact_sensor_handler is not None:
            try:
                from ..adaptive.contact_sensors import ContactAction

                if self._contact_sensor_handler.action != ContactAction.NONE:
                    if self._contact_sensor_handler.is_any_contact_open():
                        return True
            except (TypeError, AttributeError):
                pass

        # 3. Humidity spike
        if self._humidity_detector is not None:
            try:
                if self._humidity_detector.should_pause():
                    return True
            except (TypeError, AttributeError):
                pass

        # 4. Water temperature ramp / post-write settling window
        return self._water_temp_gate

    # ------------------------------------------------------------------
    # Control pause – used for deciding whether to stop the actuator
    # ------------------------------------------------------------------

    def is_control_paused(self, hvac_mode: str | None = None) -> bool:
        """Return True if heating/cooling control should be paused.

        Uses the delay-aware and mode-sensitive contact check rather than the
        simple "any open" check so that brief door openings don't immediately
        cut heat.  Learning grace is intentionally excluded here because it
        adjusts the setpoint rather than pausing the actuator.

        Checks (in priority order):
        1. Contact sensor delay elapsed *and* action resolves to PAUSE for
           the current HVAC mode.
        2. Humidity spike active.

        Args:
            hvac_mode: Current HVAC mode string ("heat", "cool", …) used to
                determine whether a contact-open event should trigger PAUSE vs.
                FROST_PROTECTION.  Pass ``None`` when the mode is unknown.

        Returns:
            True if *any* control-pause condition is active; False otherwise.
        """
        # 1. Contact sensor – delay-aware and mode-aware
        if self._contact_sensor_handler is not None:
            try:
                if self._contact_sensor_handler.should_take_action():
                    from ..adaptive.contact_sensors import ContactAction

                    if self._contact_sensor_handler.get_action(hvac_mode) == ContactAction.PAUSE:
                        return True
            except (TypeError, AttributeError):
                pass

        # 2. Humidity spike
        if self._humidity_detector is not None:
            try:
                if self._humidity_detector.should_pause():
                    return True
            except (TypeError, AttributeError):
                pass

        return False
