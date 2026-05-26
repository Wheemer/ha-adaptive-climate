# Critical 03: StatusManager rebuilt on every state read

**File:** `managers/state_attributes.py:639-645`

**Problem:** `_build_status_attribute` constructs new `StatusManager` per call instead of using `thermostat._status_manager`. Wastes allocations, loses internal state, re-runs `set_night_setback_controller` constantly. Comment admits test-compatibility hack.

**Fix:**
1. Use `thermostat._status_manager` (cached).
2. Update tests to inject a real or mock `_status_manager` on the thermostat.
3. Remove the inline constructor.

**Test:** Unit: assert single instance across N attribute reads. Integration: existing status tests pass with cached manager.

**Risk:** Med. Touches test fixtures.

**Depends on:** none.

**Blocks:** C04, C05.
