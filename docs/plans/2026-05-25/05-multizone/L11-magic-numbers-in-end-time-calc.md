# Low 11: Magic minute offsets in end-time calc

**File:** `managers/night_setback_calculator.py:124-168`

**Problem:** +60/+30/+15/-30/-45 buried in code.

**Fix:**
1. Extract to module constants with descriptive names + comments.

**Test:** Existing tests still pass.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
