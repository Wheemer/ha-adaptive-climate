# Medium 30: Bumpless skip-criteria uses already-overwritten setpoint

**File:** `pid_controller/__init__.py:538-539,350`

**Problem:** `_set_point = set_point` happens before bumpless check; if no calc ran between mode flip and resume, `_last_set_point == _set_point` even when user changed setpoint. Skip-on-large-delta misses.

**Fix:**
1. Capture `_set_point_before_calc = self._set_point` before line 538 overwrite.
2. Use that in `prepare_bumpless_transfer` setpoint-delta check.
3. Or move bumpless call before the overwrite.

**Test:** Unit: OFF→change setpoint→AUTO, assert bumpless skip when delta large.

**Risk:** Low.

**Depends on:** C02.

**Blocks:** none.
