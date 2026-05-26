# Medium 23: `get_cycle_count` defaults to HEAT for cooling zones

**File:** `managers/learning_gate.py:105-106`

**Problem:** Cooling-only zones always read 0 heat cycles → setback never gated.

**Fix:**
1. Pass active mode through: `cycle_count = adaptive_learner.get_cycle_count(self._active_mode)`.
2. Add mode arg to learning_gate API.
3. Cooling zone uses cooling count.

**Test:** Unit: cooling zone with 10 cool cycles → gated by count.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
