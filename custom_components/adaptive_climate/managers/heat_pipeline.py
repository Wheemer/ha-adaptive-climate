"""Track committed heat in hydronic pipelines using exponential rise/decay model."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Thermal time constants for hydronic pipe/emitter systems (seconds).
# Represents how quickly heat delivery commits as the valve opens, and how
# quickly delivery decays after the valve closes.  These are the system's
# thermal inertia, not the room time constant.
#
# floor_hydronic:  long   (~45 min) — concrete slab absorbs & releases heat slowly
# radiator:        medium (~15 min) — cast iron / steel radiator inertia
# convector:       short  (~7 min)  — quick-response fan coil
# forced_air:      very short (~2 min) — minimal duct inertia
HEATING_TYPE_TAU: dict[str, float] = {
    "floor_hydronic": 2700.0,
    "radiator": 900.0,
    "convector": 420.0,
    "forced_air": 120.0,
}

_DEFAULT_TAU: float = 900.0  # fallback if heating_type unknown


@dataclass
class HeatPipeline:
    """Track heat in-flight through manifold pipes using exponential rise/decay.

    Models hydronic heat delivery as an exponential process:
    - Rise (valve open):    Q(t) = Q_max * (1 - exp(-t / tau))
    - Decay (valve closed): Q(t) = Q_at_close * exp(-t / tau)

    Where ``Q_max = transport_delay`` (seconds of equivalent heat delivery) and
    ``tau`` is the thermal time constant of the piping/emitter system.

    Attributes:
        transport_delay: Time for water to travel manifold to zone (seconds).
        valve_time: Time for valve to fully open/close (seconds).
        tau: Thermal time constant for exponential model (seconds).
    """

    transport_delay: float
    valve_time: float
    tau: float = _DEFAULT_TAU
    _valve_opened_at: float | None = field(default=None, repr=False)
    _valve_closed_at: float | None = field(default=None, repr=False)
    # Committed heat snapshot captured the instant valve_closed() is called
    _q_at_close: float = field(default=0.0, repr=False)

    @staticmethod
    def tau_for_heating_type(heating_type: str | None) -> float:
        """Return thermal time constant for a heating type.

        Args:
            heating_type: HeatingType string value (e.g. "floor_hydronic") or None.

        Returns:
            Tau in seconds for the given heating type, or ``_DEFAULT_TAU`` if unknown.
        """
        if heating_type is None:
            return _DEFAULT_TAU
        return HEATING_TYPE_TAU.get(heating_type, _DEFAULT_TAU)

    # ------------------------------------------------------------------
    # Valve event hooks
    # ------------------------------------------------------------------

    def valve_opened(self, at: float) -> None:
        """Record the valve-open command timestamp (monotonic).

        Resets the close state so the rise curve restarts from zero.

        Args:
            at: Monotonic timestamp when the open command was sent.
        """
        self._valve_opened_at = at
        self._valve_closed_at = None
        self._q_at_close = 0.0

    def valve_closed(self, at: float) -> None:
        """Record the valve-close command timestamp and snapshot committed heat.

        Captures the in-flight heat level at the moment of closure so the
        decay curve can start from that level.

        Args:
            at: Monotonic timestamp when the close command was sent.
        """
        if self._valve_opened_at is not None and self.tau > 0 and self.transport_delay > 0:
            time_open = max(0.0, at - self._valve_opened_at)
            self._q_at_close = self.transport_delay * (1.0 - math.exp(-time_open / self.tau))
        else:
            self._q_at_close = 0.0
        self._valve_closed_at = at

    def reset(self) -> None:
        """Clear all valve timing state (e.g. after mode change or emergency stop)."""
        self._valve_opened_at = None
        self._valve_closed_at = None
        self._q_at_close = 0.0

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def committed_heat_remaining(self, now: float) -> float:
        """Seconds of heat delivery equivalent still in-flight.

        Uses exponential physics matched to the heating type's thermal inertia:

        While valve is open, committed heat rises toward ``transport_delay``::

            Q(t) = transport_delay * (1 - exp(-delta_t / tau))

        After valve closes, it decays from the snapshot taken at closure::

            Q(t) = Q_at_close * exp(-delta_t_since_close / tau)

        Args:
            now: Current monotonic time.

        Returns:
            Seconds of equivalent heat delivery still arriving.  Zero when
            valve has never opened or when ``transport_delay == 0``.
        """
        if self._valve_opened_at is None or self.tau <= 0 or self.transport_delay <= 0:
            return 0.0

        if self._valve_closed_at is None:
            # Valve still open — rising toward transport_delay
            time_open = max(0.0, now - self._valve_opened_at)
            return self.transport_delay * (1.0 - math.exp(-time_open / self.tau))

        # Valve closed — decaying from snapshot
        time_since_close = max(0.0, now - self._valve_closed_at)
        return self._q_at_close * math.exp(-time_since_close / self.tau)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def calculate_valve_open_duration(
        self,
        requested_duty: float,
        pwm_period: float,
        committed: float,
    ) -> float:
        """Calculate how long to keep valve open this cycle.

        Args:
            requested_duty: Target duty cycle 0.0-1.0.
            pwm_period: PWM period in seconds.
            committed: Seconds of heat already in-flight.

        Returns:
            Seconds to keep valve open (0 if committed heat covers the request).
        """
        desired_heat = requested_duty * pwm_period
        needed_heat = desired_heat - committed

        if needed_heat <= 0:
            return 0.0

        # Add half valve-actuation time for the close-command lead
        return needed_heat + (self.valve_time / 2)
