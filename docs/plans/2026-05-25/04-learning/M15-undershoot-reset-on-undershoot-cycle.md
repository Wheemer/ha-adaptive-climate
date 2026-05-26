# Medium 15: Counter resets on cycle that barely reaches target

**File:** `adaptive/undershoot_detector.py:191-195`

**Problem:** Resets when `rise_time is not None` even if `undershoot >= threshold`.

**Fix:**
1. Reset only when `rise_time is not None AND undershoot < threshold`.
2. Update tests.

**Test:** Unit: cycle reaches target then immediately fails → counter does NOT reset.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
