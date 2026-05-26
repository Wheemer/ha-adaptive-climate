# High 03: min_closed_time gates against last cycle start, not last state change

**File:** `managers/heater_controller.py:704`

**Problem:** `time.monotonic() - get_cycle_start_time() >= self._min_closed_time` — `get_cycle_start_time` is last state change, name misleading. Also asymmetric: no symmetric `effective_min_open_time` check for valve actuators.

**Fix:**
1. Rename `get_cycle_start_time` → `get_last_state_change_time` (or add alias) to clarify semantics.
2. Add symmetric `effective_min_open_time` check on valve path for short-pulse protection.
3. Add docstring on the asymmetry rationale (compressor lifespan vs valve travel).

**Test:** Unit test rapid on/off → assert min_closed_time enforced; rapid off/on for valve → assert min_open_time enforced.

**Risk:** Low-Med — symmetric check may change valve cycling cadence.

**Depends on:** none.

**Blocks:** none.
