# Low 04: Redundant valve timer handle nulling inside callbacks

**File:** `managers/heater_controller.py:309, 325`

**Problem:** `_valve_open_timer = None` / `_valve_close_timer = None` assigned inside delayed callbacks. `cancel_pending_timers()` already clears handles — redundant but harmless.

**Fix:**
1. Remove redundant assignments OR leave with a comment explaining idempotency.

**Test:** N/A.

**Risk:** Low.

**Depends on:** H01.

**Blocks:** none.
