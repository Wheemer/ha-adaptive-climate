# Critical 04: calculate_undershoot uses pre-cycle cold temperatures

**File:** `managers/cycle_metrics.py:421`

**Problem:** Raw `temperature_history` starts at cold pre-cycle temp. Every recovery cycle reports undershoot = `target - start_temp` even when target was reached. Feeds UndershootDetector → false Ki ramps on cold mornings (floor_hydronic ≥0.4°C threshold trips reliably).

**Fix:**
1. Compute `settling_start = self.get_settling_start_time()`.
2. Filter `settling_history = [(t,v) for t,v in temperature_history if settling_start is None or t >= settling_start]`.
3. Call `calculate_undershoot(settling_history or temperature_history, target_temp)`.

**Test:** Unit test recovery cycle starting 3°C below target that reaches target — assert undershoot ≈ 0, not 3.0. Regression: UndershootDetector consecutive-failure count does not increment on clean recovery.

**Risk:** Low — pure filter, fallback to raw if empty.

**Depends on:** none.

**Blocks:** `04-learning` UndershootDetector tuning (cross-ref).
