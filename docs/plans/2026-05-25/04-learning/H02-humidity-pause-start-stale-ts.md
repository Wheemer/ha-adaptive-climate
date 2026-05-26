# High 02: `_pause_start` uses stale `_last_timestamp`

**File:** `adaptive/humidity_detector.py:167-168, 183-184`

**Problem:** `_pause_start = _last_timestamp` could be previous-reading ts or None if `_check_triggers` called pre-`record_humidity`.

**Fix:**
1. Pass `ts` arg explicitly into `_check_triggers(ts, ...)`.
2. Set `self._pause_start = ts` directly.
3. Same in `_update_state` (already has `ts` in scope, currently discarded).

**Test:** Unit: trigger from cold start with no prior reading → `_pause_start` set to current ts.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
