# Low 15: integral restore accepts bool (subclass of int)

**File:** `state_restorer.py:130`

**Problem:** `bool` is `int`; `True`/`False` passes isinstance check.

**Fix:**
1. Add `not isinstance(integral_value, bool)` guard.

**Test:** Unit: restore with `True`; assert rejected.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
