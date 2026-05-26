"""Aggregate health monitor for the adaptive learning stack.

Combines three separate cumulative caps/metrics into a single 0–100 health
score so operators can see at a glance whether the learning stack as a whole
is behaving within acceptable bounds.

Signals aggregated
------------------
- **Ki multiplier** – ``UndershootDetector.cumulative_ki_multiplier``.
  Starts at 1.0; each undershoot boost increases it.  A multiplier above 1.5
  indicates the system is persistently undershooting and needing repeated
  integral boosts.

- **PID drift** – percentage by which the current gains have drifted from the
  physics baseline, via ``ValidationManager.calculate_drift_from_baseline``.
  High drift means adaptive tuning has moved significantly from the original
  physics-calculated starting point.

- **Maintenance cap usage** – fraction of the maintenance-cycle confidence cap
  that has been consumed, via ``ConfidenceContributionTracker``.  Near-full
  cap means the zone is trapped doing only maintenance cycles with no room
  to grow confidence further.

Score formula
-------------
Start at 100 and subtract per-signal penalties:

- Ki multiplier: −20 per 0.5× above 1.5 (max −60 at 3.0×)
- Drift:         linear 0 → −30 between 25 % and 50 % drift
- Cap usage:     linear 0 → −20 between 80 % and 100 % cap usage

Final score clamped to [0, 100].  Status mapping:

- ≥ 70 → HEALTHY
- ≥ 40 → WARNING
- <  40 → CRITICAL
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .confidence_contribution import ConfidenceContributionTracker
    from .undershoot_detector import UndershootDetector
    from .validation import ValidationManager

from ..const import (
    MAINTENANCE_CONFIDENCE_CAP,
    MAX_CUMULATIVE_DRIFT_PCT,
    MAX_UNDERSHOOT_KI_MULTIPLIER,
    HeatingType,
)

# ---------------------------------------------------------------------------
# HealthStatus enum
# ---------------------------------------------------------------------------


class HealthStatus(StrEnum):
    """Overall health status of the adaptive learning stack."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Penalty / score parameters
# ---------------------------------------------------------------------------

# Ki multiplier thresholds
_KI_THRESHOLD = 1.5  # start penalising above this value
_KI_STEP_SIZE = 0.5  # one step = 0.5× above threshold
_KI_PENALTY_PER_STEP = 20.0  # points deducted per step

# Maximum possible Ki penalty (e.g. at MAX_UNDERSHOOT_KI_MULTIPLIER = 3.0
# that is (3.0 - 1.5) / 0.5 * 20 = 60 points)
_KI_MAX_PENALTY = (MAX_UNDERSHOOT_KI_MULTIPLIER - _KI_THRESHOLD) / _KI_STEP_SIZE * _KI_PENALTY_PER_STEP

# Drift thresholds — expressed as fractions (not percentages)
_DRIFT_WARNING_THRESHOLD = (MAX_CUMULATIVE_DRIFT_PCT / 2) / 100.0  # 25 % → 0.25
_DRIFT_MAX_THRESHOLD = MAX_CUMULATIVE_DRIFT_PCT / 100.0  # 50 % → 0.50
_DRIFT_MAX_PENALTY = 30.0

# Maintenance cap usage thresholds
_CAP_WARNING_THRESHOLD = 0.80  # penalise above 80 % of the cap
_CAP_MAX_PENALTY = 20.0

# Status score boundaries
_HEALTHY_MIN = 70
_WARNING_MIN = 40


# ---------------------------------------------------------------------------
# HealthReport dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HealthReport:
    """Snapshot of learning health computed at a single point in time.

    Attributes
    ----------
    score:
        Aggregate health score in [0, 100].  Higher is healthier.
    status:
        Categorical summary derived from *score*.
    penalty_ki:
        Points deducted for elevated Ki cumulative multiplier.
    penalty_drift:
        Points deducted for excessive PID drift from physics baseline.
    penalty_cap:
        Points deducted for high maintenance confidence cap usage.
    ki_multiplier:
        Raw Ki cumulative multiplier from UndershootDetector.
    drift_pct:
        Raw PID drift as a fraction (0.30 = 30 %).  0.0 when no baseline.
    cap_usage_pct:
        Raw maintenance contribution as a fraction of the cap (1.0 = 100 %).
    """

    score: int
    status: HealthStatus
    penalty_ki: float
    penalty_drift: float
    penalty_cap: float
    ki_multiplier: float
    drift_pct: float
    cap_usage_pct: float


# ---------------------------------------------------------------------------
# LearningHealthMonitor
# ---------------------------------------------------------------------------


class LearningHealthMonitor:
    """Aggregates adaptive-learning signals into a single health score.

    This class is stateless — it holds references to the three source objects
    but performs no internal bookkeeping.  Call :meth:`assess` at any time to
    get a fresh :class:`HealthReport`.

    Parameters
    ----------
    heating_type:
        Heating system type, used to look up the maintenance confidence cap.
    undershoot_detector:
        Source for the Ki cumulative multiplier signal.
    validation_manager:
        Source for the PID drift from physics baseline signal.
    contribution_tracker:
        Source for the maintenance confidence cap usage signal.
    """

    def __init__(
        self,
        heating_type: HeatingType,
        undershoot_detector: UndershootDetector,
        validation_manager: ValidationManager,
        contribution_tracker: ConfidenceContributionTracker,
    ) -> None:
        self._heating_type = heating_type
        self._undershoot_detector = undershoot_detector
        self._validation_manager = validation_manager
        self._contribution_tracker = contribution_tracker

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assess(
        self,
        current_kp: float | None = None,
        current_ki: float | None = None,
        current_kd: float | None = None,
    ) -> HealthReport:
        """Compute the current learning health score.

        Parameters
        ----------
        current_kp:
            Current proportional gain.  Pass ``None`` to skip drift calculation
            (drift penalty will be 0).
        current_ki:
            Current integral gain.  Pass ``None`` to skip drift calculation.
        current_kd:
            Current derivative gain.  Pass ``None`` to skip drift calculation.

        Returns
        -------
        HealthReport
            Immutable snapshot with score, status, and per-signal breakdown.
        """
        ki_multiplier, penalty_ki = self._ki_signal()
        drift_pct, penalty_drift = self._drift_signal(current_kp, current_ki, current_kd)
        cap_usage_pct, penalty_cap = self._cap_signal()

        raw = 100.0 - penalty_ki - penalty_drift - penalty_cap
        score = max(0, min(100, round(raw)))
        status = _score_to_status(score)

        return HealthReport(
            score=score,
            status=status,
            penalty_ki=penalty_ki,
            penalty_drift=penalty_drift,
            penalty_cap=penalty_cap,
            ki_multiplier=ki_multiplier,
            drift_pct=drift_pct,
            cap_usage_pct=cap_usage_pct,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ki_signal(self) -> tuple[float, float]:
        """Return (ki_multiplier, penalty)."""
        ki_multiplier = self._undershoot_detector.cumulative_ki_multiplier
        penalty = _compute_ki_penalty(ki_multiplier)
        return ki_multiplier, penalty

    def _drift_signal(
        self,
        current_kp: float | None,
        current_ki: float | None,
        current_kd: float | None,
    ) -> tuple[float, float]:
        """Return (drift_pct, penalty).

        drift_pct is 0.0 when any gain argument is None or no baseline is set.
        """
        if current_kp is None or current_ki is None or current_kd is None:
            return 0.0, 0.0
        drift_pct = self._validation_manager.calculate_drift_from_baseline(current_kp, current_ki, current_kd)
        return drift_pct, _compute_drift_penalty(drift_pct)

    def _cap_signal(self) -> tuple[float, float]:
        """Return (cap_usage_pct, penalty)."""
        cap = MAINTENANCE_CONFIDENCE_CAP.get(self._heating_type, 0.30)
        contribution = self._contribution_tracker.maintenance_contribution
        cap_usage_pct = (contribution / cap) if cap > 0 else 0.0
        return cap_usage_pct, _compute_cap_penalty(cap_usage_pct)


# ---------------------------------------------------------------------------
# Pure-function penalty calculators (importable for tests)
# ---------------------------------------------------------------------------


def _compute_ki_penalty(ki_multiplier: float) -> float:
    """Compute penalty from Ki cumulative multiplier.

    0 when multiplier ≤ 1.5; −20 per 0.5× above threshold; capped at
    ``_KI_MAX_PENALTY``.
    """
    excess = max(0.0, ki_multiplier - _KI_THRESHOLD)
    return min(_KI_MAX_PENALTY, excess / _KI_STEP_SIZE * _KI_PENALTY_PER_STEP)


def _compute_drift_penalty(drift_pct: float) -> float:
    """Compute penalty from PID drift fraction.

    0 when drift ≤ 25 %; linear 0 → ``_DRIFT_MAX_PENALTY`` from 25 % to 50 %.
    """
    excess = max(0.0, drift_pct - _DRIFT_WARNING_THRESHOLD)
    drift_range = _DRIFT_MAX_THRESHOLD - _DRIFT_WARNING_THRESHOLD
    if drift_range <= 0.0:
        return 0.0
    return min(_DRIFT_MAX_PENALTY, excess / drift_range * _DRIFT_MAX_PENALTY)


def _compute_cap_penalty(cap_usage_pct: float) -> float:
    """Compute penalty from maintenance cap usage fraction.

    0 when usage ≤ 80 %; linear 0 → ``_CAP_MAX_PENALTY`` from 80 % to 100 %.
    """
    excess = max(0.0, cap_usage_pct - _CAP_WARNING_THRESHOLD)
    usage_range = 1.0 - _CAP_WARNING_THRESHOLD  # 0.20
    if usage_range <= 0.0:
        return 0.0
    return min(_CAP_MAX_PENALTY, excess / usage_range * _CAP_MAX_PENALTY)


def _score_to_status(score: int) -> HealthStatus:
    """Map a 0-100 score to :class:`HealthStatus`."""
    if score >= _HEALTHY_MIN:
        return HealthStatus.HEALTHY
    if score >= _WARNING_MIN:
        return HealthStatus.WARNING
    return HealthStatus.CRITICAL
