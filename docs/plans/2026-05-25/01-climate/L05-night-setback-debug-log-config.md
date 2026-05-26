# Low 05: debug log emits full config dict unconditionally

**File:** `custom_components/adaptive_climate/climate.py:213`

**Problem:** Always formats dict; minor cost.

**Fix:**
1. Wrap: `if _LOGGER.isEnabledFor(logging.DEBUG): _LOGGER.debug(...)`.

**Test:** None.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
