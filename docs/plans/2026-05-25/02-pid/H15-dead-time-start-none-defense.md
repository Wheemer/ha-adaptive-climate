# High 15: `_dead_time_start = None` would silently disable dead time

**File:** `pid_controller/__init__.py:303-307,462`

**Problem:** If `_input_time` is None when `_accumulate_integral` assigns `_dead_time_start = self._input_time`, dead time disabled forever.

**Fix:**
1. At line 462 entry, raise `ValueError("input_time must be set before _accumulate_integral")` if `_input_time is None`.
2. Or fall-through to `base * dt_hours` with debug log.
3. Add invariant comment documenting order requirement.

**Test:** Unit: call _accumulate_integral with _input_time=None, assert exception.

**Risk:** Low. Defensive.

**Depends on:** none.

**Blocks:** none.
