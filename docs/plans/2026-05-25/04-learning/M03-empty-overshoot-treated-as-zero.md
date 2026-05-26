# Medium 03: Empty overshoot list treated as 0 → false "perfectly tuned"

**File:** `adaptive/learning.py:683-700`

**Problem:** `overshoot_values=[]` → `avg_overshoot=0.0`; when all cycles have None overshoot, system thinks perfect.

**Fix:**
1. Return `None` when `len(overshoot_values) == 0`.
2. Caller branches: None → skip adjustment, log "insufficient data".
3. Distinguish from `0.0` (real measurement).

**Test:** Unit: all-None cycles → no adjustment, debug log says "no overshoot data".

**Risk:** Low.

**Depends on:** none.

**Blocks:** H12.
