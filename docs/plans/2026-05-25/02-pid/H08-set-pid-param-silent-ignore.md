# High 8: `set_pid_param` silently ignores non-numeric / accepts NaN

**File:** `pid_controller/__init__.py:382-391`

**Problem:** `isinstance(kp, (int, float))` skips strings silently; NaN passes isinstance check and poisons all subsequent calcs.

**Fix:**
1. Replace isinstance gate with explicit validation.
2. Raise `TypeError` for non-numeric.
3. Raise `ValueError` for NaN / Inf / negative (use `math.isfinite()` and `>= 0`).
4. Apply same pattern to `set_feedforward`, `set_external_temp` setters.

**Test:** Unit: pass NaN/Inf/-5/"abc", assert appropriate exception.

**Risk:** Low. May expose callers passing bad data — that's the point.

**Depends on:** none.

**Blocks:** H09 (gains_manager validation).
