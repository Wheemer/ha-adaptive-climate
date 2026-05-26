# Medium 25: `check_degradation` no cooldown → notification storm

**File:** `managers/comfort_degradation.py:43-55`

**Problem:** Same low score fires repeatedly until average improves.

**Fix:**
1. Add `self._last_alert_at: datetime | None = None`.
2. Skip if `now - last_alert_at < MIN_ALERT_INTERVAL` (e.g. 1h).
3. Reset cooldown when alert clears.

**Test:** Unit: low score repeats every 5min → first alert fires, next blocked until 1h passes.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
