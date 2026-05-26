# Low 04: Overshoot iterates full cycle history every 5min

**File:** `sensors/performance.py:574`

**Problem:** Full iteration for 1000+ cycles wasteful.

**Fix:**
1. Limit to last N (e.g., 20) cycles: `cycle_history[-20:]`.

**Test:** Unit: feed 100 cycles; assert last 20 used.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
