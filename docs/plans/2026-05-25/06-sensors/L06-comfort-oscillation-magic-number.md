# Low 06: oscillations * 10.0 magic number

**File:** `sensors/comfort.py:236`

**Problem:** Constant `10.0` undocumented.

**Fix:**
1. Add named constant `OSCILLATION_PENALTY_PER_CYCLE = 10.0`.
2. Document max-10-oscillation expectation.

**Test:** N/A.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
