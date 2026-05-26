# High 14: Cap-exactly returns no-op multiplier but still applies

**File:** `adaptive/undershoot_detector.py:269`

**Problem:** When `cumulative == CAP`, `max_allowed = 1.0` → applied multiplier `1.0`. No actual change but `_consecutive_failures` resets and `last_adjustment_time` recorded → caller logs spurious "0% increase" and decreases confidence.

**Fix:**
1. In `check_undershoot_adjustment`, if computed multiplier `<= 1.0 + EPS` (e.g. 1.001), return `None`.
2. Skip side effects entirely.

**Test:** Unit: cumulative at cap → `check_undershoot_adjustment` returns None, no state mutation.

**Risk:** Low.

**Depends on:** C08.

**Blocks:** none.
