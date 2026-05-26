# High 04: async_call_later lambdas capture stale hvac_mode

**File:** `managers/heater_controller.py:725-729, 805-811, 1002-1006, 1033-1037`

**Problem:** Deferred lambdas capture `hvac_mode`/`was_clamped` at scheduling time. Mode change during 2×PWM debounce → events emitted with stale mode → CycleTrackerManager rejects or misroutes (see `_on_settling_started` line 403).

**Fix:**
1. Lambdas re-read live mode via callback (`lambda _: self._emit_with_current_mode(...)`).
2. Hook `cancel_pending_timers()` into climate entity's `async_set_hvac_mode` path (not just `force=True` turn_off).
3. Add `if self._cycle_active` guard to `_emit_heating_started_delayed` (covers M04).

**Test:** Unit test schedule emit → mode flip mid-debounce → assert event uses new mode OR is cancelled.

**Risk:** Med — touches lifecycle integration with climate entity.

**Depends on:** C03 (related state machine).

**Blocks:** M04 (subsumed).
