# Medium 08: _on_cycle_started doesn't cancel prior settling timeout

**File:** `managers/cycle_tracker.py:583-599, 380`

**Problem:** `_reset_cycle_state` cancels settling timeout on abort, but `_on_cycle_started` doesn't. Old timer can finalize a brand-new cycle midway.

**Fix:**
1. Add `self._cancel_settling_timeout()` at start of `_on_cycle_started` (line ~380).
2. Add comment explaining the precedence rule.

**Test:** Unit test SETTLING_STARTED → quick CYCLE_STARTED before timeout fires → assert old timeout cancelled, new cycle not finalized.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
