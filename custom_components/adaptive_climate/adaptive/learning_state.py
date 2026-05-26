"""LearningState dataclass — snapshot of AdaptiveLearner convergence state.

Used by LearningCoordinator to expose a clean, typed summary of learning
progress to callers (climate.py, sensors, services) without requiring
direct access to AdaptiveLearner internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.components.climate import HVACMode

    from .learning import AdaptiveLearner


@dataclass
class LearningState:
    """Snapshot of adaptive learning state for a specific HVAC mode.

    Attributes:
        confidence: Convergence confidence in [0.0, 1.0].
        status: Human-readable tier string: idle | collecting | stable | tuned | optimized.
        cycle_count: Total cycles recorded for this mode.
        heating_cycle_count: Heating-mode cycles.
        cooling_cycle_count: Cooling-mode cycles.
        auto_apply_count: Number of auto-applied PID adjustments for this mode.
        last_adjustment_time: Wall-clock timestamp of last PID recommendation.
        in_validation_mode: Whether post-auto-apply validation is active.
        consecutive_converged_cycles: Consecutive cycles meeting convergence criteria.
        pid_converged_for_ke: Whether PID is stable enough for Ke learning.
    """

    confidence: float = 0.0
    status: str = "collecting"
    cycle_count: int = 0
    heating_cycle_count: int = 0
    cooling_cycle_count: int = 0
    auto_apply_count: int = 0
    last_adjustment_time: datetime | None = None
    in_validation_mode: bool = False
    consecutive_converged_cycles: int = 0
    pid_converged_for_ke: bool = False

    # Extra metadata for diagnostics
    extra: dict = field(default_factory=dict)


def get_learning_state(learner: AdaptiveLearner, mode: HVACMode | None = None) -> LearningState:
    """Build a LearningState snapshot from a live AdaptiveLearner instance.

    Args:
        learner: AdaptiveLearner to snapshot.
        mode: HVACMode (HEAT or COOL) to use for mode-specific fields.
              Defaults to HEAT when None.

    Returns:
        LearningState populated from the learner's current state.
    """
    from ..managers.state_attributes import _compute_learning_status  # type: ignore[import]

    confidence = learner.get_convergence_confidence(mode)
    auto_apply_count = learner.get_auto_apply_count(mode)
    cycle_count = learner.get_cycle_count(mode)

    try:
        status = _compute_learning_status(learner, mode)
    except Exception:
        # Fall back to a simple tier derivation if state_attributes module unavailable
        status = _simple_status(confidence, cycle_count)

    return LearningState(
        confidence=confidence,
        status=status,
        cycle_count=cycle_count,
        heating_cycle_count=len(learner._heating_cycle_history),
        cooling_cycle_count=len(learner._cooling_cycle_history),
        auto_apply_count=auto_apply_count,
        last_adjustment_time=learner.get_last_adjustment_time(),
        in_validation_mode=learner.is_in_validation_mode(),
        consecutive_converged_cycles=learner.get_consecutive_converged_cycles(),
        pid_converged_for_ke=learner.is_pid_converged_for_ke(),
    )


def _simple_status(confidence: float, cycle_count: int) -> str:
    """Fallback status derivation using fixed confidence tiers.

    Args:
        confidence: Convergence confidence in [0.0, 1.0].
        cycle_count: Number of recorded cycles.

    Returns:
        Status string: idle | collecting | stable | tuned | optimized.
    """
    if cycle_count < 6:
        return "collecting"
    if confidence >= 0.95:
        return "optimized"
    if confidence >= 0.56:
        return "tuned"
    if confidence >= 0.32:
        return "stable"
    return "collecting"
