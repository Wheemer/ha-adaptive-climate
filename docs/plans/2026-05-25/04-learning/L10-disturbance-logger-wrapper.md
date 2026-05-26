# Low 10: `self._logger = _LOGGER` wrapper adds nothing

**File:** `adaptive/disturbance_detector.py:21-23`

**Problem:** Redundant indirection.

**Fix:**
1. Use `_LOGGER` directly throughout module.
2. Remove `self._logger`.

**Test:** Existing tests pass.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
