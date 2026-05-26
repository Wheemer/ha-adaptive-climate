# Critical 06: NotificationManager uses naive `datetime.now()`

**File:** `managers/notification_manager.py:96, 105`

**Problem:** `datetime.now()` returns naive local time. DST jumps / timezone changes make cooldowns appear elapsed instantly or never. Project rule: `dt_util.utcnow()` for wall-clock, `time.monotonic()` for elapsed.

**Fix:**
1. Convert `_cooldowns` to `dict[str, float]`.
2. Replace `datetime.now()` with `time.monotonic()`.
3. Compare elapsed via `time.monotonic() - last < cooldown_seconds`.
4. Drop any `datetime` imports no longer needed.

**Test:** Unit: trigger notification, simulate `time.monotonic` advancing, assert cooldown enforcement. Verify no naive datetimes serialized.

**Risk:** Low — local refactor.

**Depends on:** none.

**Blocks:** none.
