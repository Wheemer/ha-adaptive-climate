# Medium 16: `_ke_controller is not None` guard silently fails apply

**File:** `custom_components/adaptive_climate/climate.py:1245`

**Problem:** `async_apply_adaptive_ke` silently no-ops when controller is None. No log/error.

**Fix:**
1. Log WARNING when guard fails with reason ("ke_controller not initialized").
2. Or raise `RuntimeError` if call is invalid in that state.

**Test:** Unit: call with ke_controller=None → warning logged.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
