# Critical 02: confidence_raw leaks between zones in loop

**File:** `services/scheduled.py:340` (and ~239)

**Problem:** `confidence_raw` defined inside `if adaptive_learner:` block. When zone N has learner and zone N+1 doesn't, stale value from N leaks into N+1's `ZoneSnapshot`.

**Fix:**
1. Initialize `confidence_raw = None` at top of each zone loop iteration.
2. Audit other vars in same loop body for same pattern (cycles, status, etc.).
3. Add test with mixed-learner zone list.

**Test:** Unit test snapshot loop with 3 zones: learner / no-learner / learner; assert per-zone fields isolated.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
