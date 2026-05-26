# Medium 20: `delta_multiplier` can go below 1.0 on race

**File:** `adaptive/cycle_weight.py:99-100`

**Problem:** If `is_recovery=True` but `starting_delta < threshold` (race on is_stable change), multiplier <1.0; recovery weight < maintenance.

**Fix:**
1. Clamp: `delta_multiplier = max(1.0, min(delta_multiplier, DELTA_MULTIPLIER_CAP))`.

**Test:** Unit: delta < threshold + is_recovery=True → multiplier = 1.0.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
