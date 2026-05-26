# Medium 08: `weather.get_forecasts` shape change silently returns None

**File:** `managers/auto_mode_switching.py:131-145`

**Problem:** If HA renames `forecast` → `forecasts`, silent None return.

**Fix:**
1. Add `_LOGGER.debug` of raw result keys.
2. Validate expected shape, log warning if missing.

**Test:** Unit: pass response with renamed key, assert warning logged.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
