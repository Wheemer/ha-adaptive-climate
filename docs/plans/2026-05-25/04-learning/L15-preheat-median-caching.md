# Low 15: `statistics.median` recomputed each call

**File:** `adaptive/preheat.py:285-290`

**Problem:** O(N log N) per call; fine at N=20 but accumulates.

**Fix:**
1. Cache median per bin; invalidate on add/prune.
2. Or defer (profile first).

**Test:** Benchmark before/after for high-update scenario.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Profile-driven? Skip unless evidence.
