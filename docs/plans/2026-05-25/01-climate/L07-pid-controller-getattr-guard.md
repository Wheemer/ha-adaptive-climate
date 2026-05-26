# Low 07: unnecessary `getattr(self, "_pid_controller", None)` guard

**File:** `custom_components/adaptive_climate/climate.py:1063`

**Problem:** `_pid_controller` always set in `__init__`; legacy guard.

**Fix:** Replace `getattr` with `self._pid_controller is not None` or drop guard.

**Test:** Tests pass.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
