"""Tests for LearningHealthMonitor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.adaptive_climate.adaptive.learning_health_monitor import (
    HealthReport,
    HealthStatus,
    LearningHealthMonitor,
    _compute_cap_penalty,
    _compute_drift_penalty,
    _compute_ki_penalty,
    _score_to_status,
    _CAP_MAX_PENALTY,
    _CAP_WARNING_THRESHOLD,
    _DRIFT_MAX_PENALTY,
    _DRIFT_WARNING_THRESHOLD,
    _KI_MAX_PENALTY,
    _HEALTHY_MIN,
    _WARNING_MIN,
)
from custom_components.adaptive_climate.const import HeatingType


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_monitor(
    heating_type: HeatingType = HeatingType.RADIATOR,
    ki_multiplier: float = 1.0,
    drift_return: float = 0.0,
    maintenance_contribution: float = 0.0,
) -> LearningHealthMonitor:
    """Build a LearningHealthMonitor with mocked signal sources."""
    undershoot = MagicMock()
    undershoot.cumulative_ki_multiplier = ki_multiplier

    validation = MagicMock()
    validation.calculate_drift_from_baseline.return_value = drift_return

    contribution = MagicMock()
    contribution.maintenance_contribution = maintenance_contribution

    return LearningHealthMonitor(
        heating_type=heating_type,
        undershoot_detector=undershoot,
        validation_manager=validation,
        contribution_tracker=contribution,
    )


# ---------------------------------------------------------------------------
# Unit tests — penalty calculators
# ---------------------------------------------------------------------------


class TestComputeKiPenalty:
    """Tests for _compute_ki_penalty."""

    def test_no_penalty_at_baseline(self):
        """No penalty when multiplier is exactly at the warning threshold."""
        assert _compute_ki_penalty(1.0) == pytest.approx(0.0)
        assert _compute_ki_penalty(1.5) == pytest.approx(0.0)

    def test_penalty_starts_above_threshold(self):
        """Penalty starts above _KI_THRESHOLD (1.5)."""
        # 2.0 is 1 step above 1.5 → 20 pts
        assert _compute_ki_penalty(2.0) == pytest.approx(20.0)

    def test_penalty_increases_linearly(self):
        """Penalty increases 20 pts per 0.5× above threshold."""
        assert _compute_ki_penalty(2.0) == pytest.approx(20.0)
        assert _compute_ki_penalty(2.5) == pytest.approx(40.0)
        assert _compute_ki_penalty(3.0) == pytest.approx(60.0)

    def test_penalty_capped_at_max(self):
        """Penalty is capped even if multiplier exceeds MAX_UNDERSHOOT_KI_MULTIPLIER."""
        assert _compute_ki_penalty(10.0) == pytest.approx(_KI_MAX_PENALTY)

    def test_penalty_zero_below_threshold(self):
        """Values below warning threshold produce zero penalty."""
        assert _compute_ki_penalty(0.5) == pytest.approx(0.0)
        assert _compute_ki_penalty(1.0) == pytest.approx(0.0)
        assert _compute_ki_penalty(1.49) == pytest.approx(0.0, abs=0.5)


class TestComputeDriftPenalty:
    """Tests for _compute_drift_penalty."""

    def test_no_penalty_below_warning_threshold(self):
        """No penalty when drift is at or below the warning threshold (25 %)."""
        assert _compute_drift_penalty(0.0) == pytest.approx(0.0)
        assert _compute_drift_penalty(0.25) == pytest.approx(0.0)

    def test_full_penalty_at_max_threshold(self):
        """Full penalty when drift reaches MAX_CUMULATIVE_DRIFT_PCT (50 %)."""
        assert _compute_drift_penalty(0.50) == pytest.approx(_DRIFT_MAX_PENALTY)

    def test_linear_between_thresholds(self):
        """Penalty is linear between 25 % and 50 % drift."""
        mid = _DRIFT_WARNING_THRESHOLD + (0.50 - _DRIFT_WARNING_THRESHOLD) / 2  # 37.5 %
        expected = _DRIFT_MAX_PENALTY / 2
        assert _compute_drift_penalty(mid) == pytest.approx(expected)

    def test_penalty_capped_beyond_max(self):
        """Penalty capped at _DRIFT_MAX_PENALTY when drift > 50 %."""
        assert _compute_drift_penalty(1.0) == pytest.approx(_DRIFT_MAX_PENALTY)


class TestComputeCapPenalty:
    """Tests for _compute_cap_penalty."""

    def test_no_penalty_below_warning_threshold(self):
        """No penalty when cap usage is at or below 80 %."""
        assert _compute_cap_penalty(0.0) == pytest.approx(0.0)
        assert _compute_cap_penalty(0.80) == pytest.approx(0.0)

    def test_full_penalty_at_100_percent(self):
        """Full penalty when cap usage reaches 100 %."""
        assert _compute_cap_penalty(1.0) == pytest.approx(_CAP_MAX_PENALTY)

    def test_linear_between_thresholds(self):
        """Penalty is linear between 80 % and 100 % cap usage."""
        mid = _CAP_WARNING_THRESHOLD + (1.0 - _CAP_WARNING_THRESHOLD) / 2  # 90 %
        expected = _CAP_MAX_PENALTY / 2
        assert _compute_cap_penalty(mid) == pytest.approx(expected)

    def test_penalty_capped_beyond_full(self):
        """Penalty capped when usage exceeds 100 %."""
        assert _compute_cap_penalty(1.5) == pytest.approx(_CAP_MAX_PENALTY)


class TestScoreToStatus:
    """Tests for _score_to_status."""

    def test_healthy_at_and_above_threshold(self):
        assert _score_to_status(_HEALTHY_MIN) == HealthStatus.HEALTHY
        assert _score_to_status(100) == HealthStatus.HEALTHY

    def test_warning_between_thresholds(self):
        assert _score_to_status(_WARNING_MIN) == HealthStatus.WARNING
        assert _score_to_status(_HEALTHY_MIN - 1) == HealthStatus.WARNING

    def test_critical_below_warning_threshold(self):
        assert _score_to_status(_WARNING_MIN - 1) == HealthStatus.CRITICAL
        assert _score_to_status(0) == HealthStatus.CRITICAL


# ---------------------------------------------------------------------------
# Unit tests — LearningHealthMonitor
# ---------------------------------------------------------------------------


class TestLearningHealthMonitorHealthy:
    """All signals nominal → healthy score."""

    def test_all_nominal_is_healthy(self):
        """No penalties applied when all signals are within safe bounds."""
        monitor = _make_monitor(
            ki_multiplier=1.0,
            drift_return=0.0,
            maintenance_contribution=0.0,
        )
        report = monitor.assess(current_kp=1.5, current_ki=0.01, current_kd=10.0)

        assert report.score == 100
        assert report.status == HealthStatus.HEALTHY
        assert report.penalty_ki == pytest.approx(0.0)
        assert report.penalty_drift == pytest.approx(0.0)
        assert report.penalty_cap == pytest.approx(0.0)

    def test_ki_at_warning_threshold_no_penalty(self):
        """Ki multiplier at exactly 1.5 produces no penalty."""
        monitor = _make_monitor(ki_multiplier=1.5)
        report = monitor.assess()
        assert report.penalty_ki == pytest.approx(0.0)
        assert report.score == 100


class TestLearningHealthMonitorKiPenalty:
    """Ki multiplier drives penalty correctly."""

    def test_ki_2x_deducts_20(self):
        """Multiplier 2.0 → penalty 20 → score 80."""
        monitor = _make_monitor(ki_multiplier=2.0)
        report = monitor.assess()
        assert report.ki_multiplier == pytest.approx(2.0)
        assert report.penalty_ki == pytest.approx(20.0)
        assert report.score == 80
        assert report.status == HealthStatus.HEALTHY

    def test_ki_2p5x_deducts_40(self):
        """Multiplier 2.5 → penalty 40 → score 60."""
        monitor = _make_monitor(ki_multiplier=2.5)
        report = monitor.assess()
        assert report.penalty_ki == pytest.approx(40.0)
        assert report.score == 60

    def test_ki_3x_deducts_60(self):
        """Multiplier 3.0 → penalty 60 → score 40."""
        monitor = _make_monitor(ki_multiplier=3.0)
        report = monitor.assess()
        assert report.penalty_ki == pytest.approx(60.0)
        assert report.score == 40
        # 40 is the boundary between WARNING and CRITICAL
        assert report.status == HealthStatus.WARNING


class TestLearningHealthMonitorDriftPenalty:
    """Drift signal drives penalty correctly."""

    def test_drift_below_warning_no_penalty(self):
        """25 % drift produces no penalty."""
        monitor = _make_monitor(drift_return=0.25)
        report = monitor.assess(current_kp=1.5, current_ki=0.01, current_kd=10.0)
        assert report.penalty_drift == pytest.approx(0.0)

    def test_drift_50_percent_max_penalty(self):
        """50 % drift produces max drift penalty (30 pts)."""
        monitor = _make_monitor(drift_return=0.50)
        report = monitor.assess(current_kp=1.5, current_ki=0.01, current_kd=10.0)
        assert report.penalty_drift == pytest.approx(30.0)
        assert report.drift_pct == pytest.approx(0.50)

    def test_drift_omitted_when_gains_not_provided(self):
        """No drift penalty when gains are None."""
        monitor = _make_monitor(drift_return=0.90)
        report = monitor.assess()  # no gains passed
        assert report.drift_pct == pytest.approx(0.0)
        assert report.penalty_drift == pytest.approx(0.0)

    def test_validation_called_with_gains(self):
        """ValidationManager.calculate_drift_from_baseline called with passed gains."""
        monitor = _make_monitor(drift_return=0.0)
        monitor.assess(current_kp=2.0, current_ki=0.02, current_kd=20.0)
        monitor._validation_manager.calculate_drift_from_baseline.assert_called_once_with(2.0, 0.02, 20.0)


class TestLearningHealthMonitorCapPenalty:
    """Maintenance cap usage drives penalty correctly."""

    def test_cap_usage_below_warning_no_penalty(self):
        """80 % cap usage produces no penalty."""
        # radiator cap = 0.30 → 80 % = 0.24
        monitor = _make_monitor(
            heating_type=HeatingType.RADIATOR,
            maintenance_contribution=0.30 * 0.80,  # exactly at warning threshold
        )
        report = monitor.assess()
        assert report.penalty_cap == pytest.approx(0.0)

    def test_cap_usage_100_percent_max_penalty(self):
        """100 % cap usage produces max cap penalty (20 pts)."""
        # radiator cap = 0.30 → 100 % = 0.30
        monitor = _make_monitor(
            heating_type=HeatingType.RADIATOR,
            maintenance_contribution=0.30,
        )
        report = monitor.assess()
        assert report.cap_usage_pct == pytest.approx(1.0)
        assert report.penalty_cap == pytest.approx(20.0)

    def test_cap_usage_90_percent_half_penalty(self):
        """90 % cap usage produces half the max penalty (10 pts)."""
        # radiator cap = 0.30 → 90 % = 0.27
        monitor = _make_monitor(
            heating_type=HeatingType.RADIATOR,
            maintenance_contribution=0.30 * 0.90,
        )
        report = monitor.assess()
        assert report.cap_usage_pct == pytest.approx(0.90)
        assert report.penalty_cap == pytest.approx(10.0)


class TestLearningHealthMonitorCombined:
    """Combined penalty scenarios."""

    def test_all_signals_max_penalty(self):
        """All three signals at maximum → score near 0."""
        monitor = _make_monitor(
            ki_multiplier=3.0,  # -60
            drift_return=0.50,  # -30
            maintenance_contribution=0.30,  # -20  (100 % of radiator cap)
        )
        report = monitor.assess(current_kp=1.5, current_ki=0.01, current_kd=10.0)
        # 100 - 60 - 30 - 20 = -10 → clamped to 0
        assert report.score == 0
        assert report.status == HealthStatus.CRITICAL

    def test_partial_signals_warning_range(self):
        """Score in warning range when only Ki is elevated."""
        monitor = _make_monitor(
            ki_multiplier=2.5,  # -40 → score 60
        )
        report = monitor.assess()
        assert report.score == 60
        assert report.status == HealthStatus.WARNING

    def test_report_is_immutable(self):
        """HealthReport is a frozen dataclass."""
        monitor = _make_monitor()
        report = monitor.assess()
        with pytest.raises((AttributeError, TypeError)):
            report.score = 99  # type: ignore[misc]

    def test_floor_hydronic_cap_lookup(self):
        """Cap lookup works correctly for floor_hydronic (25 % cap)."""
        # floor_hydronic cap = 0.25 → 100 % usage = 0.25
        monitor = _make_monitor(
            heating_type=HeatingType.FLOOR_HYDRONIC,
            maintenance_contribution=0.25,
        )
        report = monitor.assess()
        assert report.cap_usage_pct == pytest.approx(1.0)
        assert report.penalty_cap == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# Unit tests — AdaptiveLearner.health property
# ---------------------------------------------------------------------------


class TestAdaptiveLearnerHealthProperty:
    """Integration tests for the AdaptiveLearner.health property."""

    def _make_learner(self, heating_type: str = "radiator"):
        from custom_components.adaptive_climate.adaptive.learning import AdaptiveLearner

        return AdaptiveLearner(heating_type=heating_type)

    def test_health_property_returns_health_report(self):
        """AdaptiveLearner.health returns a HealthReport."""
        learner = self._make_learner()
        report = learner.health
        assert isinstance(report, HealthReport)

    def test_health_score_100_fresh_learner(self):
        """Fresh learner with no penalties should score 100."""
        learner = self._make_learner()
        report = learner.health
        # No gains wired → drift is skipped → only ki and cap signals
        assert report.score == 100
        assert report.status == HealthStatus.HEALTHY
        assert report.penalty_ki == pytest.approx(0.0)
        assert report.penalty_drift == pytest.approx(0.0)

    def test_health_degrades_after_undershoot_boosts(self):
        """Health score decreases when Ki multiplier is elevated."""
        learner = self._make_learner()
        # Simulate two boosts: 1.0 × 1.25 × 1.25 = 1.5625 (slight above threshold)
        learner._undershoot_detector.cumulative_ki_multiplier = 2.0
        report = learner.health
        assert report.penalty_ki == pytest.approx(20.0)
        assert report.score == 80

    def test_health_uses_gains_manager_when_wired(self):
        """When PIDGainsManager is wired, drift is computed from current gains."""
        from custom_components.adaptive_climate.const import PIDGains

        learner = self._make_learner()

        # Set a physics baseline so drift can be computed
        learner._validation.set_physics_baseline(kp=1.0, ki=0.01, kd=10.0)

        # Wire a mock PIDGainsManager returning gains at baseline (0 % drift)
        mock_manager = MagicMock()
        mock_manager.get_gains.return_value = PIDGains(kp=1.0, ki=0.01, kd=10.0)
        learner._pid_gains_manager = mock_manager

        report = learner.health
        # At baseline → drift_pct = 0 → no penalty
        assert report.drift_pct == pytest.approx(0.0)
        assert report.penalty_drift == pytest.approx(0.0)
        mock_manager.get_gains.assert_called_once()

    def test_health_all_heating_types(self):
        """health property works for all supported heating types."""
        for ht in ("floor_hydronic", "radiator", "convector", "forced_air"):
            learner = self._make_learner(heating_type=ht)
            report = learner.health
            assert isinstance(report, HealthReport)
            assert 0 <= report.score <= 100
