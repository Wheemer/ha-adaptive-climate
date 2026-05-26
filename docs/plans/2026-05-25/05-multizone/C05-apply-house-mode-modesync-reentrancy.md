# Critical 05: `_apply_house_mode` triggers redundant ModeSync fan-out

**File:** `coordinator.py:640-666`

**Problem:** Iterates zones calling `set_hvac_mode` service. First child zone's state change re-enters `ModeSync.on_mode_change`; `_sync_in_progress` False, ModeSync starts redundant fan-out to other N-1 zones. O(N) wasted service calls per auto-mode switch + race against original loop.

**Fix:**
1. Acquire `mode_sync._sync_in_progress = True` before loop in `_apply_house_mode`.
2. Reset to False in `finally`.
3. Or: introduce dedicated cross-component re-entrancy lock owned by coordinator.
4. Add log when redundant entry is suppressed for diagnostics.

**Test:** Unit: mock `ModeSync.on_mode_change`, call `_apply_house_mode` with 5 zones, assert no re-entrant invocation. Integration: enable auto-mode switching, count service calls per switch.

**Risk:** Med — concurrency; ensure flag reset on exception.

**Depends on:** none.

**Blocks:** none.
