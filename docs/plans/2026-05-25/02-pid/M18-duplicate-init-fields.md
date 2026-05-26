# Medium 18: Duplicate field initializations in `PID.__init__`

**File:** `pid_controller/__init__.py:110-128`

**Problem:** `self._proportional` initialized at lines 110 (float) and 127 (int); same for `_derivative`.

**Fix:**
1. Delete duplicates at lines 127-128.
2. Standardize on `0.0` (float).

**Test:** Tests still pass.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
