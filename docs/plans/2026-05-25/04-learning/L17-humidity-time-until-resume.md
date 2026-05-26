# Low 17: `get_time_until_resume` uses stale `_last_timestamp`

**File:** `adaptive/humidity_detector.py:205-220`

**Problem:** Time freezes between sensor readings.

**Fix:**
1. Replace `_last_timestamp` usage with `dt_util.utcnow()` for elapsed calc.
2. Use `_stabilization_start` (or `_pause_start`) as origin.

**Test:** Unit: no new readings for 2 min → `get_time_until_resume()` decreases by 2 min.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
