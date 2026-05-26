# High 08: Turn-off debounce task field mutated outside lock

**File:** `central_controller.py:269-311, 336, 361`

**Problem:** Tasks created under lock, but `finally` blocks reassign `_heater_turnoff_task = None` without lock. Race: `done()` check passes on task whose `finally` still pending → double-schedule.

**Fix:**
1. Wrap task field reset in `async with self._startup_lock:` inside `finally`.
2. Or use atomic CAS-style: re-acquire lock, check identity matches before clearing.
3. Document lock invariant in class docstring.

**Test:** Unit: stress concurrent `update()` calls; assert no double-schedule.

**Risk:** Med — concurrency, careful to avoid deadlock with parent acquirer.

**Depends on:** C07.

**Blocks:** none.
