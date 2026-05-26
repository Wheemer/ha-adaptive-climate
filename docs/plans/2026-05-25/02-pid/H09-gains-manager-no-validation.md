# High 9: `PIDGainsManager.set_gains` accepts NaN/Inf/negative

**File:** `managers/pid_gains_manager.py:113-155`

**Problem:** kp/ki/kd/ke passed straight through. Negative Kp inverts controller; NaN poisons disk persistence.

**Fix:**
1. At top of `set_gains`, validate each non-None gain: `math.isfinite()` and `>= 0`.
2. Raise `ValueError(f"Invalid gain {name}={value}")`.
3. Validate before `replace()` to avoid partial state mutation.
4. Add same guard in `_migrate_history_entry`.

**Test:** Unit: set_gains(kp=float('nan')), assert ValueError, gains unchanged.

**Risk:** Low.

**Depends on:** H08.

**Blocks:** M22 (PIDTuningManager validation).
