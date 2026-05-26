# High 03: EMA Euler discretization unstable for irregular sampling

**File:** `coordinator.py:224-236`

**Problem:** `alpha = dt / tau` only stable for `dt << tau`. Consecutive events 6h apart overwrite EMA almost entirely.

**Fix:**
1. Replace with exponential: `alpha = 1 - math.exp(-dt / (tau * 3600))`.
2. Keep `min(1.0, alpha)` safety clamp.
3. Document tau units (hours) in calculation.
4. Add unit test for large dt fidelity.

**Test:** Unit: feed 6h gap events, assert EMA decays smoothly, not overwritten. Compare against analytical first-order response.

**Risk:** Low — math fix.

**Depends on:** H02.

**Blocks:** none.
