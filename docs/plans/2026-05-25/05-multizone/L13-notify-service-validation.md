# Low 13: `notify_service` accepts both prefixed/unprefixed silently

**File:** `managers/notification_manager.py:62-65`

**Problem:** Accepts `"mobile_app_iphone"` and `"notify.mobile_app_iphone"`; drops domain prefix silently.

**Fix:**
1. Validate at config-flow.
2. Log warning if prefix present in user input.

**Test:** Unit: both forms produce same call args.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
