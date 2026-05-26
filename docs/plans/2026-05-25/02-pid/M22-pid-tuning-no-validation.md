# Medium 22: `PIDTuningManager.async_set_pid` accepts negative/Inf gains

**File:** `managers/pid_tuning.py:62-83`

**Problem:** `float(kp)` etc forwarded to `_gains_manager.set_gains` without validation. Service call `set_pid kp=-5` flips controller.

**Fix:**
1. With H09 in place, validation cascades from gains_manager — verify it does.
2. Add explicit validation at service boundary for clearer error to user.
3. Raise `ValueError` with user-friendly message (HA exposes as service error).

**Test:** Service call with kp=-5, assert ValueError surfaces in HA.

**Risk:** Low.

**Depends on:** H09.

**Blocks:** none.
