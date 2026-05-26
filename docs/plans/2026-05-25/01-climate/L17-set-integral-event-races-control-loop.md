# Low 17: `_handle_set_integral_event` mutates PID internals without lock

**File:** `custom_components/adaptive_climate/__init__.py:680-694`

**Problem:** Reaches into `_pid_controller.integral` and `_i` directly without `_temp_lock`. Races control loop.

**Fix:**
1. Add public `async_set_integral(value)` method on entity acquiring `_temp_lock`.
2. Event handler calls it.

**Test:** Unit: concurrent set_integral + control loop → final integral matches set value.

**Risk:** Low — but related to C01 race class.

**Depends on:** C01.

**Blocks:** none.
