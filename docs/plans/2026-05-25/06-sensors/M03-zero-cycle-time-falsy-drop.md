# Medium 03: last_cycle_time=0 dropped via falsy check

**File:** `sensors/performance.py:399-405`

**Problem:** `if last_cycle_time:` drops 0.0. Use `is not None`.

**Fix:**
1. Replace truthy check with `is not None`.

**Test:** Unit: last_cycle_time=0.0; assert attribute present.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
