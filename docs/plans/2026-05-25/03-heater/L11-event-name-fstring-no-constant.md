# Low 11: heater_control_failed event name is inline f-string

**File:** `managers/heater_controller.py:583-590`

**Problem:** No `EVENT_*` constant; easy to typo in listeners.

**Fix:**
1. Add `EVENT_HEATER_CONTROL_FAILED = f"{DOMAIN}_heater_control_failed"` in `const.py`.
2. Use the constant in `bus.async_fire`.

**Test:** Existing tests; grep for raw string usage.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
