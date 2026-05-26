# High 16: Hard-coded reason strings drift from `PIDChangeReason` enum

**File:** `adaptive/learning.py:1429-1436`

**Problem:** Reads both `"undershoot_ki_boost"` and `"chronic_approach_ki_boost"` but codebase only writes `PIDChangeReason.UNDERSHOOT_BOOST`. If enum `.value` differs from either string, both reads return None → cross-restart cooldown silently disabled.

**Fix:**
1. Verify `PIDChangeReason.UNDERSHOOT_BOOST.value` (likely `"undershoot_boost"`).
2. Replace hard-coded strings with `PIDChangeReason.UNDERSHOOT_BOOST.value`.
3. Remove backward-compat `"chronic_approach_ki_boost"` read (or document as legacy with date).

**Test:** Unit: write entry via gains_manager → learning reads it correctly; restart cooldown enforced.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
