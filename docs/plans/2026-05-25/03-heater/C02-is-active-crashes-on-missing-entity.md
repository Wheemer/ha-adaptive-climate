# Critical 02: is_active() crashes + silently skips entities

**File:** `managers/heater_controller.py:553-567`

**Problem:** `states.get(entity).state` raises `AttributeError` on missing entity; `except` is outside loop so one bad entity aborts entire manifold check returning False. Also `STATE_UNAVAILABLE`/`STATE_UNKNOWN` fall through to `float("unknown")` → ValueError.

**Fix:**
1. Move null/unavailable guard inside the loop.
2. `state_obj = self._hass.states.get(entity); if state_obj is None or state_obj.state in (STATE_UNKNOWN, STATE_UNAVAILABLE): continue`.
3. Keep AttributeError catch as defense-in-depth around `.state` access.

**Test:** Unit test multi-entity manifold with one entity missing — assert other entities still evaluated. Test STATE_UNAVAILABLE returns False without ValueError log.

**Risk:** Low — narrow scope, additive guard.

**Depends on:** none.

**Blocks:** none.
