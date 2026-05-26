# Arch 06: Relocate `NotificationManager` to `helpers/`

**File:** `managers/notification_manager.py`

**Problem:** Not manager-like (no state machine, no Protocol). Misplaced in `managers/`.

**Fix:**
1. Move to `helpers/notifications.py`.
2. Update imports.
3. Class name unchanged or rename to `Notifier`.

**Test:** Existing tests pass.

**Risk:** Low — pure move.

**Depends on:** none.

**Blocks:** none.
