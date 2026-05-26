# High 01: dead `_restore_state` / `_restore_pid_values` compatibility wrappers

**File:** `custom_components/adaptive_climate/climate.py:823-837`

**Problem:** Both methods construct fresh `StateRestorer(self)` per call, reach into single-underscore privates. No callers (grep-confirmed). Re-instantiate restorer rather than using the one in `async_added_to_hass`.

**Fix:**
1. Grep again to confirm zero callers.
2. Delete both methods.
3. If any caller surfaces, replace with single delegating call to cached `self._state_restorer`.

**Test:** Run full pytest; pyright check; HA reload smoke test.

**Risk:** Low — pure deletion.

**Depends on:** none.

**Blocks:** none.
