# High 16: `decay_integral` accepts negative factor

**File:** `pid_controller/__init__.py:318-325`

**Problem:** Negative factor flips integral sign. Currently no caller passes negative, but no guard.

**Fix:**
1. Clamp: `factor = max(0.0, min(1.0, factor))`.
2. Reject NaN with `ValueError`.
3. Log warning when clamping occurred (signals caller bug).

**Test:** Unit: decay_integral(-0.5), assert integral unchanged or zeroed (not flipped).

**Risk:** Low. Covered by H10 batch.

**Depends on:** none.

**Blocks:** none.
