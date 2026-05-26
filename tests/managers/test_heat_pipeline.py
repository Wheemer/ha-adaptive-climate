"""Tests for HeatPipeline exponential rise/decay model."""

import math
from custom_components.adaptive_climate.managers.heat_pipeline import (
    HeatPipeline,
    HEATING_TYPE_TAU,
    _DEFAULT_TAU,
)


class TestTauForHeatingType:
    """Tests for tau_for_heating_type factory."""

    def test_known_heating_types(self):
        """Each heating type maps to a positive tau."""
        for htype in ("floor_hydronic", "radiator", "convector", "forced_air"):
            tau = HeatPipeline.tau_for_heating_type(htype)
            assert tau > 0, f"{htype} should have positive tau"

    def test_floor_hydronic_longest_tau(self):
        """Floor hydronic has the longest tau (most thermal inertia)."""
        assert HEATING_TYPE_TAU["floor_hydronic"] > HEATING_TYPE_TAU["radiator"]
        assert HEATING_TYPE_TAU["radiator"] > HEATING_TYPE_TAU["convector"]
        assert HEATING_TYPE_TAU["convector"] > HEATING_TYPE_TAU["forced_air"]

    def test_none_returns_default(self):
        """None heating_type returns default tau."""
        assert HeatPipeline.tau_for_heating_type(None) == _DEFAULT_TAU

    def test_unknown_type_returns_default(self):
        """Unknown heating_type returns default tau."""
        assert HeatPipeline.tau_for_heating_type("unknown_type") == _DEFAULT_TAU


class TestHeatPipelineExponentialModel:
    """Tests for committed_heat_remaining() exponential physics."""

    def test_no_committed_heat_when_never_opened(self):
        """Zero committed heat when valve has never been opened."""
        pipeline = HeatPipeline(transport_delay=600.0, valve_time=120.0, tau=900.0)
        assert pipeline.committed_heat_remaining(now=1000.0) == 0.0

    def test_no_committed_heat_when_transport_delay_zero(self):
        """Zero committed heat when transport_delay is zero (no pipes to fill)."""
        pipeline = HeatPipeline(transport_delay=0.0, valve_time=120.0, tau=900.0)
        pipeline.valve_opened(at=0.0)
        assert pipeline.committed_heat_remaining(now=500.0) == 0.0

    def test_committed_heat_rises_exponentially_while_open(self):
        """Committed heat follows Q = transport_delay * (1 - exp(-t/tau)) while valve open."""
        tau = 900.0
        transport_delay = 600.0
        pipeline = HeatPipeline(transport_delay=transport_delay, valve_time=0.0, tau=tau)
        pipeline.valve_opened(at=0.0)

        for t in (60.0, 300.0, 900.0, 1800.0, 3600.0):
            expected = transport_delay * (1.0 - math.exp(-t / tau))
            actual = pipeline.committed_heat_remaining(now=t)
            assert abs(actual - expected) < 1e-9, f"At t={t}: expected {expected:.3f}, got {actual:.3f}"

    def test_committed_heat_asymptotes_toward_transport_delay(self):
        """After many tau periods, committed heat is very close to transport_delay."""
        tau = 900.0
        transport_delay = 600.0
        pipeline = HeatPipeline(transport_delay=transport_delay, valve_time=0.0, tau=tau)
        pipeline.valve_opened(at=0.0)
        # After 10 tau periods, Q ≈ transport_delay * (1 - exp(-10)) ≈ 99.995%
        assert pipeline.committed_heat_remaining(now=10 * tau) > 0.999 * transport_delay

    def test_committed_heat_never_exceeds_transport_delay(self):
        """Committed heat is bounded by transport_delay regardless of time open."""
        pipeline = HeatPipeline(transport_delay=600.0, valve_time=0.0, tau=900.0)
        pipeline.valve_opened(at=0.0)
        assert pipeline.committed_heat_remaining(now=100000.0) <= 600.0

    def test_committed_heat_at_one_tau(self):
        """At t == tau, committed heat is 63.2% of transport_delay (exp constant)."""
        tau = 900.0
        transport_delay = 600.0
        pipeline = HeatPipeline(transport_delay=transport_delay, valve_time=0.0, tau=tau)
        pipeline.valve_opened(at=0.0)
        q_at_tau = pipeline.committed_heat_remaining(now=tau)
        # (1 - 1/e) ≈ 0.6321
        assert abs(q_at_tau / transport_delay - (1.0 - math.exp(-1.0))) < 1e-9

    def test_committed_heat_decays_after_close(self):
        """After valve closes, committed heat decays exponentially from snapshot."""
        tau = 900.0
        transport_delay = 600.0
        pipeline = HeatPipeline(transport_delay=transport_delay, valve_time=0.0, tau=tau)

        # Open valve long enough to reach near-steady state
        t_open = 5 * tau  # 5 tau ≈ 99.3% of max
        pipeline.valve_opened(at=0.0)
        q_at_close = pipeline.committed_heat_remaining(now=t_open)

        pipeline.valve_closed(at=t_open)

        # After closing, should decay from q_at_close
        for dt in (60.0, 300.0, 900.0, 1800.0):
            expected = q_at_close * math.exp(-dt / tau)
            actual = pipeline.committed_heat_remaining(now=t_open + dt)
            assert abs(actual - expected) < 1e-9, f"After close +{dt}s: expected {expected:.3f}, got {actual:.3f}"

    def test_committed_heat_decays_to_near_zero_after_many_tau(self):
        """Committed heat approaches zero well after valve closes."""
        pipeline = HeatPipeline(transport_delay=600.0, valve_time=0.0, tau=900.0)
        pipeline.valve_opened(at=0.0)
        pipeline.valve_closed(at=3600.0)  # Close after 4 tau periods open
        # Q_at_close ≈ 600 * (1 - exp(-4)) ≈ 589 s
        # After 10 more tau periods: 589 * exp(-10) ≈ 0.027 s
        assert pipeline.committed_heat_remaining(now=3600.0 + 10 * 900.0) < 0.1

    def test_committed_heat_not_negative(self):
        """Committed heat never goes negative."""
        pipeline = HeatPipeline(transport_delay=600.0, valve_time=0.0, tau=900.0)
        pipeline.valve_opened(at=0.0)
        pipeline.valve_closed(at=100.0)
        assert pipeline.committed_heat_remaining(now=100000.0) >= 0.0

    def test_valve_close_short_open_time(self):
        """Brief valve open gives low committed heat that decays correctly."""
        tau = 900.0
        transport_delay = 600.0
        pipeline = HeatPipeline(transport_delay=transport_delay, valve_time=0.0, tau=tau)
        pipeline.valve_opened(at=0.0)
        t_close = 60.0  # only 1/15 tau
        pipeline.valve_closed(at=t_close)

        q_at_close = transport_delay * (1.0 - math.exp(-t_close / tau))
        # Immediately after close
        assert abs(pipeline.committed_heat_remaining(now=t_close) - q_at_close) < 1e-9
        # After another tau period of decay
        assert abs(pipeline.committed_heat_remaining(now=t_close + tau) - q_at_close * math.exp(-1.0)) < 1e-9


class TestHeatPipelineReset:
    """Tests for pipeline reset behaviour."""

    def test_reset_clears_state(self):
        """Reset clears all valve timing state."""
        pipeline = HeatPipeline(transport_delay=600.0, valve_time=120.0, tau=900.0)
        pipeline.valve_opened(at=0.0)
        pipeline.reset()
        assert pipeline.committed_heat_remaining(now=100.0) == 0.0

    def test_valve_opened_clears_close_state(self):
        """Opening valve again clears previous close snapshot."""
        pipeline = HeatPipeline(transport_delay=600.0, valve_time=0.0, tau=900.0)
        pipeline.valve_opened(at=0.0)
        pipeline.valve_closed(at=900.0)
        # Re-open: should start fresh
        pipeline.valve_opened(at=1000.0)
        # Immediately after re-open, committed heat starts from zero
        assert pipeline.committed_heat_remaining(now=1000.0) == 0.0


class TestHeatPipelineValveOpenDuration:
    """Tests for calculate_valve_open_duration (unchanged interface)."""

    def test_full_duty_no_committed(self):
        """50% duty with no committed heat: 450s heat + 60s half-valve = 510s."""
        pipeline = HeatPipeline(transport_delay=600.0, valve_time=120.0, tau=900.0)
        duration = pipeline.calculate_valve_open_duration(
            requested_duty=0.5,
            pwm_period=900.0,
            committed=0.0,
        )
        assert duration == 510.0

    def test_committed_heat_reduces_duration(self):
        """Committed heat reduces required valve open time."""
        pipeline = HeatPipeline(transport_delay=600.0, valve_time=120.0, tau=900.0)
        duration = pipeline.calculate_valve_open_duration(
            requested_duty=0.5,
            pwm_period=900.0,
            committed=200.0,
        )
        # Need (450 - 200) = 250s heat + 60s half-valve = 310s
        assert duration == 310.0

    def test_zero_when_committed_exceeds_request(self):
        """No valve open needed when committed heat covers the full request."""
        pipeline = HeatPipeline(transport_delay=600.0, valve_time=120.0, tau=900.0)
        duration = pipeline.calculate_valve_open_duration(
            requested_duty=0.3,
            pwm_period=900.0,
            committed=400.0,
        )
        assert duration == 0.0


class TestHeatPipelineTauValues:
    """Verify heating-type tau ordering matches physical expectations."""

    def test_floor_hydronic_tau_at_least_30_min(self):
        """Floor hydronic tau represents slow concrete slab response."""
        assert HEATING_TYPE_TAU["floor_hydronic"] >= 1800.0  # 30 min minimum

    def test_forced_air_tau_at_most_5_min(self):
        """Forced air tau represents fast duct response."""
        assert HEATING_TYPE_TAU["forced_air"] <= 300.0  # 5 min maximum

    def test_radiator_tau_between_floor_and_convector(self):
        """Radiator tau is between floor hydronic and convector."""
        assert HEATING_TYPE_TAU["floor_hydronic"] > HEATING_TYPE_TAU["radiator"] > HEATING_TYPE_TAU["convector"]
