# Low 12: milestone_tracker task fire-and-forget swallows exceptions

**File:** `managers/state_attributes.py:285-288`

**Problem:** `async_create_task` swallows; use `async_create_background_task` (HA 2023.5+) with name.

**Fix:**
1. `hass.async_create_background_task(coro, name="adaptive_climate_milestone_check")`.

**Test:** Unit: task with raise; assert logged.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
