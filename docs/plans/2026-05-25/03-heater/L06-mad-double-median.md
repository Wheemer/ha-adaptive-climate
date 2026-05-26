# Low 06: _calculate_mad recomputes median twice

**File:** `managers/cycle_metrics.py:215-249`

**Problem:** Trivial inefficiency / clarity.

**Fix:**
1. Use `statistics.median` once, store; compute deviations; call `statistics.median` again on deviations.
2. Adds clarity, not perf.

**Test:** Existing tests.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
