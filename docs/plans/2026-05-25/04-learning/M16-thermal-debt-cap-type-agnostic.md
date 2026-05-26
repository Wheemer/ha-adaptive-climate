# Medium 16: `_thermal_debt` cap 10.0 type-agnostic

**File:** `adaptive/undershoot_detector.py:140`

**Problem:** Hard cap `10.0 °C·h` doesn't scale per heating type. Floor=2.5h, forced_air=0.5h — same cap.

**Fix:**
1. Compute cap from threshold: `cap = 2 * SEVERE_UNDERSHOOT_MULTIPLIER * debt_threshold` (units consistent °C·min).
2. Convert to consistent unit (use minutes throughout or hours throughout — audit).

**Test:** Unit: floor_hydronic cap > forced_air cap; both ≥ 2x threshold.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
