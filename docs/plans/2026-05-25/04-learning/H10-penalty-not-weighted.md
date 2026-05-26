# High 10: Penalty path uses flat 0.05 vs weighted reward

**File:** `adaptive/learning.py:1196 vs 1208`

**Problem:** Reward path uses weighted gain w/ caps; penalty flat `CONFIDENCE_INCREASE_PER_GOOD_CYCLE * 0.5 = 0.05`. High-difficulty bad cycle penalized > clean maintenance reward → downward drift bias.

**Fix:**
1. Compute `weighted_penalty = base_penalty * cycle_weight` mirroring reward routing.
2. Apply same caps (contribution tracker) via tracker's poor-cycle method (add if missing).
3. Alternatively document why penalties are non-weighted with rationale.

**Test:** Unit: high-difficulty bad cycle penalty > maintenance bad cycle penalty; mass test shows no net drift in mixed cycle sequences.

**Risk:** Med — affects learning convergence behavior.

**Depends on:** C11 (rebate path).

**Blocks:** none.

**Unresolved:** Decision: weight penalties symmetrically or not? Defer to hvac-expert.
