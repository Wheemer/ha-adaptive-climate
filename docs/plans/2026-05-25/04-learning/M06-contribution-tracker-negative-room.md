# Medium 06: `apply_maintenance_gain` can decrement on negative room

**File:** `adaptive/confidence_contribution.py:115-143`

**Problem:** When contribution > cap, `room = cap - current < 0`; `gain <= room` is False for positive gain → falls into "crosses cap" branch with `under_cap_gain = negative` → tracker decremented.

**Fix:**
1. Add early return: `if current_contribution >= cap: return DIMINISHING_RATE * gain` (no tracker mutation, or controlled decay).
2. Restructure conditional so negative `room` is impossible to reach in "crosses cap" branch.

**Test:** Unit: tracker at cap → next call returns diminishing gain, tracker doesn't decrement.

**Risk:** Med — affects cap behavior.

**Depends on:** C11 (interacts with rebate semantics).

**Blocks:** none.
