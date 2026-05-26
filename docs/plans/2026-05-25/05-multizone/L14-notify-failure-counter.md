# Low 14: Notification failure not counted, spams logs

**File:** `managers/notification_manager.py:74, 91`

**Problem:** Broad `except` with `_LOGGER.exception` fine, but misconfigured notify spams.

**Fix:**
1. Track failure count per service.
2. After N consecutive failures, suppress and log warning.
3. Mirror `central_controller._consecutive_failures` pattern.

**Test:** Unit: simulate repeated failures, assert log suppression after threshold.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
