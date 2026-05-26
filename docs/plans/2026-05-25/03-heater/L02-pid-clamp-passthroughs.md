# Low 02: _get_pid_was_clamped / _reset_pid_clamp_state pointless indirection

**File:** `managers/heater_controller.py:188-204`

**Problem:** Passthroughs to optional callbacks add no value.

**Fix:**
1. Inline at call sites OR drop the methods and use callback directly with `None`-guard.

**Test:** Existing tests pass.

**Risk:** Low.

**Depends on:** H01 (do alongside file split).

**Blocks:** none.
