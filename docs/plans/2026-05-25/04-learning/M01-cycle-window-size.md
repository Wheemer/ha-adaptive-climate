# Medium 01: `recent_cycles` window scales unboundedly with min_cycles

**File:** `adaptive/learning.py:641`

**Problem:** `cycle_history[-min_cycles * 2:]` — when subsequent learning multiplier raises min_cycles to 8, window=16 consuming most of MAX_CYCLE_HISTORY.

**Fix:**
1. Use explicit upper bound: `window = max(min_cycles * 2, 8)` capped at e.g. `min(MAX_CYCLE_HISTORY // 2, 16)`.
2. Document buffer reservation for outlier rejection.

**Test:** Unit: window stays within `[8, 16]` regardless of min_cycles.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
