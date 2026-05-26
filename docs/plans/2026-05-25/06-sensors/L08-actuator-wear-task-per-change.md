# Low 08: actuator_wear schedules task per state change

**File:** `sensors/actuator_wear.py:124-126`

**Problem:** PWM cycling creates many tasks.

**Fix:**
1. Debounce: schedule via `async_call_later` with 5-10s coalesce.

**Test:** Unit: 100 changes/sec; assert ≤1 task per debounce window.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
