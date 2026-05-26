# Low 14: `_expire_old_observations` mutation-during-iter clarity

**File:** `adaptive/preheat.py:170-184`

**Problem:** Mutates list via key snapshot — safe but unclear.

**Fix:**
1. Use dict comprehension: `self._observations = {k: [o for o in v if o.timestamp >= cutoff] for k, v in self._observations.items()}`.
2. Drop empty bins: `if v` post-filter.

**Test:** Existing tests pass.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
