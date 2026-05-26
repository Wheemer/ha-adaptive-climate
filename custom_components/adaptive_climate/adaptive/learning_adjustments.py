"""Pure-computation helpers extracted from AdaptiveLearner for PID adjustment logic.

These are standalone functions that operate on explicit parameters (no `self`),
making them independently testable and reusable by LearningCoordinator.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
import logging

from homeassistant.util import dt as dt_util

from ..const import (
    CLAMPED_OVERSHOOT_MULTIPLIER,
    DEFAULT_CLAMPED_OVERSHOOT_MULTIPLIER,
    MIN_CONVERGENCE_CYCLES_FOR_KE,
)
from .robust_stats import robust_average

if TYPE_CHECKING:
    from .cycle_analysis import CycleMetrics
    from .undershoot_detector import UndershootDetector

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PID history helpers (moved from learning.py module scope)
# ---------------------------------------------------------------------------


def get_last_adjustment_time_from_history(
    pid_history: list[dict],
    reason: str,
) -> datetime | None:
    """Get the timestamp of the last Ki adjustment for a given reason.

    Args:
        pid_history: List of PID history entries from PIDGainsManager
        reason: The reason string to filter by (e.g., "undershoot_ki_boost")

    Returns:
        datetime in UTC if found, None otherwise
    """
    for entry in reversed(pid_history):
        if entry.get("reason") == reason:
            timestamp_str = entry.get("timestamp")
            if timestamp_str:
                try:
                    dt = datetime.fromisoformat(timestamp_str)
                except (ValueError, TypeError):
                    _LOGGER.warning("Could not parse PID history timestamp: %s", timestamp_str)
                    continue
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
    return None


def get_physics_baseline_ki_from_history(pid_history: list[dict]) -> float | None:
    """Get the physics baseline Ki from PID history.

    Looks for the most recent entry with reason "physics_init" or "physics_reset".
    Falls back to None if no physics entry exists (to avoid using boosted baseline).

    Args:
        pid_history: List of PID history entries from PIDGainsManager.

    Returns:
        Ki value from the most recent physics entry, or None if not found.
    """
    if not pid_history:
        return None

    for entry in reversed(pid_history):
        reason = entry.get("reason", "")
        if reason in ("physics_init", "physics_reset"):
            ki = entry.get("ki")
            if ki is not None:
                return float(ki)

    return None


# ---------------------------------------------------------------------------
# Convergence and rate limiting (extracted from AdaptiveLearner methods)
# ---------------------------------------------------------------------------


def check_convergence(
    convergence_thresholds: dict,
    avg_overshoot: float,
    avg_oscillations: float,
    avg_settling_time: float,
    avg_rise_time: float,
    avg_inter_cycle_drift: float = 0.0,
    avg_settling_mae: float = 0.0,
    avg_undershoot: float = 0.0,
) -> bool:
    """Check if the system has converged (all metrics within acceptable bounds).

    Args:
        convergence_thresholds: Dict with overshoot_max, oscillations_max, etc.
        avg_overshoot: Average overshoot in °C
        avg_oscillations: Average number of oscillations
        avg_settling_time: Average settling time in minutes
        avg_rise_time: Average rise time in minutes
        avg_inter_cycle_drift: Average inter-cycle drift in °C
        avg_settling_mae: Average settling MAE in °C
        avg_undershoot: Average undershoot in °C

    Returns:
        True if all metrics are within their thresholds.
    """
    is_converged = (
        avg_overshoot <= convergence_thresholds["overshoot_max"]
        and avg_oscillations <= convergence_thresholds["oscillations_max"]
        and avg_settling_time <= convergence_thresholds["settling_time_max"]
        and avg_rise_time <= convergence_thresholds["rise_time_max"]
        and abs(avg_inter_cycle_drift) <= convergence_thresholds.get("inter_cycle_drift_max", 0.3)
        and avg_settling_mae <= convergence_thresholds.get("settling_mae_max", 0.3)
        and avg_undershoot <= convergence_thresholds.get("undershoot_max", 0.2)
    )

    if is_converged:
        _LOGGER.info(
            "PID convergence detected - system tuned: "
            "overshoot=%.2f°C, oscillations=%.1f, settling=%.1fmin, rise=%.1fmin, "
            "inter_cycle_drift=%.2f°C, settling_mae=%.2f°C, undershoot=%.2f°C",
            avg_overshoot,
            avg_oscillations,
            avg_settling_time,
            avg_rise_time,
            avg_inter_cycle_drift,
            avg_settling_mae,
            avg_undershoot,
        )

    return is_converged


def check_rate_limit(
    last_adjustment_time: datetime | None,
    cycles_since_last_adjustment: int,
    min_interval_hours: int,
    min_cycles: int,
) -> bool:
    """Check hybrid rate limit (both time AND cycle gates must be satisfied).

    Args:
        last_adjustment_time: Timestamp of last PID adjustment (or None for first).
        cycles_since_last_adjustment: Cycles elapsed since last adjustment.
        min_interval_hours: Minimum hours between adjustments.
        min_cycles: Minimum cycles between adjustments.

    Returns:
        True if rate-limited (skip adjustment), False if OK to proceed.
    """
    if last_adjustment_time is None:
        return False

    time_since_last = dt_util.utcnow() - last_adjustment_time
    min_interval = timedelta(hours=min_interval_hours)
    time_gate_satisfied = time_since_last >= min_interval
    cycle_gate_satisfied = cycles_since_last_adjustment >= min_cycles

    if not time_gate_satisfied:
        hours_remaining = (min_interval - time_since_last).total_seconds() / 3600
        _LOGGER.info(
            "PID adjustment rate limited (time gate): last adjustment was %.1fh ago, "
            "minimum interval is %dh (%.1fh remaining)",
            time_since_last.total_seconds() / 3600,
            min_interval_hours,
            hours_remaining,
        )
        return True

    if not cycle_gate_satisfied:
        cycles_remaining = min_cycles - cycles_since_last_adjustment
        _LOGGER.info(
            "PID adjustment rate limited (cycle gate): %d cycles since last adjustment, "
            "minimum is %d cycles (%d cycles remaining)",
            cycles_since_last_adjustment,
            min_cycles,
            cycles_remaining,
        )
        return True

    return False


# ---------------------------------------------------------------------------
# Cycle metric averaging (extracted from calculate_pid_adjustment body)
# ---------------------------------------------------------------------------


def compute_cycle_averages(
    cycle_history: list,
    min_cycles: int,
    heating_type: str | None,
) -> dict[str, Any] | None:
    """Compute robust-averaged metrics from recent undisturbed cycle history.

    Filters disturbed cycles, applies outlier rejection, and computes averages
    for all metrics used by the PID rule engine.

    Args:
        cycle_history: Full history list for the current HVAC mode.
        min_cycles: Minimum undisturbed cycles required to proceed.
        heating_type: Heating type string for clamped-overshoot multiplier lookup.

    Returns:
        Dict with avg_overshoot, avg_undershoot, avg_oscillations, avg_rise_time,
        avg_settling_time, avg_inter_cycle_drift, avg_settling_mae,
        avg_decay_contribution, avg_integral_at_tolerance,
        outdoor_temp_values, rise_time_values — or None if insufficient data.
    """
    # Filter and select recent undisturbed cycles
    recent_cycles = cycle_history[-(min_cycles * 2) :]
    undisturbed_cycles = [c for c in recent_cycles if not c.is_disturbed]

    if len(undisturbed_cycles) < min_cycles:
        _LOGGER.debug(
            "Insufficient undisturbed cycles for learning: %d undisturbed of %d total (need %d)",
            len(undisturbed_cycles),
            len(recent_cycles),
            min_cycles,
        )
        return None

    recent_cycles = undisturbed_cycles[-min_cycles:]

    # Overshoot: prefer controllable_overshoot (excludes committed heat)
    clamped_multiplier = CLAMPED_OVERSHOOT_MULTIPLIER.get(heating_type, DEFAULT_CLAMPED_OVERSHOOT_MULTIPLIER)
    clamped_count = 0
    split_count = 0
    overshoot_values: list[float] = []
    for c in recent_cycles:
        overshoot_value = getattr(c, "controllable_overshoot", None)
        if overshoot_value is not None:
            split_count += 1
        else:
            overshoot_value = c.overshoot
        if overshoot_value is not None:
            if getattr(c, "was_clamped", False):
                overshoot_values.append(overshoot_value * clamped_multiplier)
                clamped_count += 1
            else:
                overshoot_values.append(overshoot_value)

    if overshoot_values:
        avg_overshoot, overshoot_outliers = robust_average(overshoot_values)
        if overshoot_outliers:
            _LOGGER.debug(
                "Removed %d overshoot outliers from %d cycles",
                len(overshoot_outliers),
                len(overshoot_values),
            )
        if clamped_count > 0:
            _LOGGER.debug(
                "%d of %d recent cycles clamped, overshoot amplified by %.1fx (%s)",
                clamped_count,
                len(overshoot_values),
                clamped_multiplier,
                heating_type,
            )
        if split_count > 0:
            _LOGGER.debug(
                "%d of %d cycles using controllable overshoot (excluding committed heat)",
                split_count,
                len(overshoot_values),
            )
    else:
        avg_overshoot = 0.0

    undershoot_values = [c.undershoot for c in recent_cycles if c.undershoot is not None]
    avg_undershoot = 0.0
    if undershoot_values:
        avg_undershoot, undershoot_outliers = robust_average(undershoot_values)
        if undershoot_outliers:
            _LOGGER.debug("Removed %d undershoot outliers", len(undershoot_outliers))

    settling_time_values = [c.settling_time for c in recent_cycles if c.settling_time is not None]
    avg_settling_time = 0.0
    if settling_time_values:
        avg_settling_time, settling_outliers = robust_average(settling_time_values)
        if settling_outliers:
            _LOGGER.debug("Removed %d settling_time outliers", len(settling_outliers))

    oscillation_values = [c.oscillations for c in recent_cycles]
    avg_oscillations, oscillation_outliers = robust_average(oscillation_values)
    if oscillation_outliers:
        _LOGGER.debug("Removed %d oscillation outliers", len(oscillation_outliers))

    rise_time_values = [c.rise_time for c in recent_cycles if c.rise_time is not None]
    avg_rise_time = 0.0
    if rise_time_values:
        avg_rise_time, rise_outliers = robust_average(rise_time_values)
        if rise_outliers:
            _LOGGER.debug("Removed %d rise_time outliers", len(rise_outliers))

    outdoor_temp_values = [c.outdoor_temp_avg for c in recent_cycles if c.outdoor_temp_avg is not None]

    decay_values = [c.decay_contribution for c in recent_cycles if c.decay_contribution is not None]
    avg_decay_contribution = statistics.mean(decay_values) if decay_values else None

    integral_at_tolerance_values = [
        c.integral_at_tolerance_entry for c in recent_cycles if c.integral_at_tolerance_entry is not None
    ]
    avg_integral_at_tolerance = statistics.mean(integral_at_tolerance_values) if integral_at_tolerance_values else None

    drift_values = [c.inter_cycle_drift for c in recent_cycles if c.inter_cycle_drift is not None]
    avg_inter_cycle_drift = sum(drift_values) / len(drift_values) if drift_values else 0.0

    mae_values = [c.settling_mae for c in recent_cycles if c.settling_mae is not None]
    avg_settling_mae = sum(mae_values) / len(mae_values) if mae_values else 0.0

    _LOGGER.debug(
        "Learning evaluation using %d cycles: avg_overshoot=%.3f, avg_undershoot=%.3f, "
        "avg_oscillations=%.1f, avg_settling_time=%.1f, avg_rise_time=%.1f, "
        "avg_inter_cycle_drift=%.3f, avg_settling_mae=%.3f, avg_decay=%.3f",
        len(recent_cycles),
        avg_overshoot,
        avg_undershoot,
        avg_oscillations,
        avg_settling_time,
        avg_rise_time,
        avg_inter_cycle_drift,
        avg_settling_mae,
        avg_decay_contribution or 0.0,
    )

    return {
        "avg_overshoot": avg_overshoot,
        "avg_undershoot": avg_undershoot,
        "avg_oscillations": avg_oscillations,
        "avg_rise_time": avg_rise_time,
        "avg_settling_time": avg_settling_time,
        "avg_inter_cycle_drift": avg_inter_cycle_drift,
        "avg_settling_mae": avg_settling_mae,
        "avg_decay_contribution": avg_decay_contribution,
        "avg_integral_at_tolerance": avg_integral_at_tolerance,
        "outdoor_temp_values": outdoor_temp_values,
        "rise_time_values": rise_time_values,
        "recent_cycles_count": len(recent_cycles),
    }


# ---------------------------------------------------------------------------
# Rule application (extracted from calculate_pid_adjustment body)
# ---------------------------------------------------------------------------


def apply_rules_to_gains(
    rule_results: list,
    learning_rate: float,
    kp: float,
    ki: float,
    kd: float,
) -> tuple[float, float, float]:
    """Apply PID rule results with learning-rate scaling.

    Args:
        rule_results: List of PIDRuleResult objects (already conflict-resolved).
        learning_rate: Multiplier in [0.5, 2.0] from convergence confidence.
        kp: Current proportional gain.
        ki: Current integral gain.
        kd: Current derivative gain.

    Returns:
        Tuple of (new_kp, new_ki, new_kd) after applying all rule adjustments.
    """
    new_kp, new_ki, new_kd = kp, ki, kd

    for result in rule_results:
        scaled_kp_factor = 1.0 + (result.kp_factor - 1.0) * learning_rate
        scaled_ki_factor = 1.0 + (result.ki_factor - 1.0) * learning_rate
        scaled_kd_factor = 1.0 + (result.kd_factor - 1.0) * learning_rate

        if result.kp_factor != 1.0:
            _LOGGER.info("%s: Kp *= %.2f (scaled: %.2f)", result.reason, result.kp_factor, scaled_kp_factor)
        if result.ki_factor != 1.0:
            _LOGGER.info("%s: Ki *= %.2f (scaled: %.2f)", result.reason, result.ki_factor, scaled_ki_factor)
        if result.kd_factor != 1.0:
            _LOGGER.info("%s: Kd *= %.2f (scaled: %.2f)", result.reason, result.kd_factor, scaled_kd_factor)

        new_kp *= scaled_kp_factor
        new_ki *= scaled_ki_factor
        new_kd *= scaled_kd_factor

    return new_kp, new_ki, new_kd


# ---------------------------------------------------------------------------
# Convergence tracking (extracted from AdaptiveLearner.update_convergence_tracking)
# ---------------------------------------------------------------------------


def update_convergence_tracking(learner: Any, metrics: CycleMetrics) -> bool:
    """Update convergence tracking for Ke learning activation.

    Tracks consecutive converged cycles and sets `_pid_converged_for_ke` when
    the threshold is met. Resets counter on any non-converged cycle.

    Args:
        learner: AdaptiveLearner instance (accesses _convergence_thresholds, etc.)
        metrics: The latest cycle metrics to evaluate.

    Returns:
        True if PID is now converged for Ke learning, False otherwise.
    """
    overshoot = metrics.overshoot if metrics.overshoot is not None else 0.0
    undershoot = metrics.undershoot if metrics.undershoot is not None else 0.0
    oscillations = metrics.oscillations
    settling_time = metrics.settling_time if metrics.settling_time is not None else 0.0
    rise_time = metrics.rise_time if metrics.rise_time is not None else 0.0

    thresholds = learner._convergence_thresholds
    is_cycle_converged = (
        overshoot <= thresholds["overshoot_max"]
        and undershoot <= thresholds.get("undershoot_max", 0.2)
        and oscillations <= thresholds["oscillations_max"]
        and settling_time <= thresholds["settling_time_max"]
        and rise_time <= thresholds["rise_time_max"]
    )

    if is_cycle_converged:
        learner._consecutive_converged_cycles += 1
        _LOGGER.debug(
            "Convergence tracking: cycle converged (%d consecutive)",
            learner._consecutive_converged_cycles,
        )
        if learner._consecutive_converged_cycles >= MIN_CONVERGENCE_CYCLES_FOR_KE and not learner._pid_converged_for_ke:
            learner._pid_converged_for_ke = True
            _LOGGER.info(
                "PID converged for Ke learning after %d consecutive cycles",
                learner._consecutive_converged_cycles,
            )
    else:
        if learner._consecutive_converged_cycles > 0:
            _LOGGER.debug(
                "Convergence tracking: cycle not converged, resetting counter (was %d)",
                learner._consecutive_converged_cycles,
            )
        learner._consecutive_converged_cycles = 0
        learner._pid_converged_for_ke = False

    return learner._pid_converged_for_ke


# ---------------------------------------------------------------------------
# Historic scan (extracted from AdaptiveLearner._perform_historic_scan)
# ---------------------------------------------------------------------------


def perform_historic_scan(cycle_history: list, undershoot_detector: UndershootDetector) -> None:
    """Scan existing cycle history for chronic approach patterns.

    Feeds all cycles to the undershoot detector's cycle mode in order and logs
    the result. Actual Ki adjustment is applied by the normal learning flow.

    Args:
        cycle_history: Heating cycle history to scan.
        undershoot_detector: UndershootDetector instance to receive cycles.
    """
    if not cycle_history:
        _LOGGER.debug("No cycle history to scan for chronic approach patterns")
        return

    _LOGGER.info("Performing historic scan of %d cycles for chronic approach patterns", len(cycle_history))

    for cycle in cycle_history:
        cycle_duration_minutes = None
        if cycle.rise_time is not None or cycle.settling_time is not None:
            cycle_duration_minutes = (cycle.rise_time or 0.0) + (cycle.settling_time or 0.0)
        undershoot_detector.add_cycle(cycle, cycle_duration_minutes)

    cycles_completed = len(cycle_history)
    if undershoot_detector.should_adjust_ki(cycles_completed):
        _LOGGER.warning(
            "Historic scan detected chronic approach pattern: %d consecutive failures",
            undershoot_detector._consecutive_failures,
        )
        _LOGGER.info(
            "Chronic approach Ki adjustment will be recommended: %.3fx multiplier",
            undershoot_detector.get_adjustment(),
        )
    else:
        _LOGGER.debug("No chronic approach pattern detected in historic scan")
