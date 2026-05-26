# Medium 04: _emit_heating_started_delayed ignores _cycle_active

**File:** `managers/heater_controller.py:295-309`

**Problem:** Fires event even after mode/abort between schedule and fire. Stale mode issue (see H04).

**Fix:**
1. Add `if not self._cycle_active: return` guard.
2. Mirror existing guard in `_emit_settling_started_debounced`.

**Test:** Unit test schedule emit → abort cycle → assert no event fires.

**Risk:** Low.

**Depends on:** H04 (overlapping fix).

**Blocks:** none.
