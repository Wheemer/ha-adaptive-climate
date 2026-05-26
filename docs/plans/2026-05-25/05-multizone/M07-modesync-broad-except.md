# Medium 07: `ModeSync._set_zone_mode` broad `except Exception`

**File:** `coordinator.py:912`

**Problem:** Masks programming errors.

**Fix:**
1. Catch `HomeAssistantError, ServiceNotFound` specifically.
2. Log unexpected with `_LOGGER.exception(...)` and re-raise or surface.

**Test:** Unit: simulate `ServiceNotFound`, assert specific handling.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
