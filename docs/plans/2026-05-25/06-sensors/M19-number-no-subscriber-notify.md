# Medium 19: number.py learning_window_days update no notify

**File:** `number.py:67-68`

**Problem:** `hass.data[DOMAIN]["learning_window_days"] = int(value)` — no notification. Scheduled tasks must re-read each tick.

**Fix:**
1. Verify `async_daily_learning` (services/scheduled.py:455) re-reads from `hass.data`.
2. If cached: refactor to re-read or emit dispatcher signal.

**Test:** Integration: change number, run scheduled task, assert new value applied.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
