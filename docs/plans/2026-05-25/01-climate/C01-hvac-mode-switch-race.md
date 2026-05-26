# Critical 01: HVAC mode switch not lock-protected

**File:** `custom_components/adaptive_climate/climate.py:1102-1166` vs `climate_control.py:31`

**Problem:** `async_set_hvac_mode` awaits `_async_heater_turn_off(force=True)` before mutating `_hvac_mode`. Control-loop tick during the await observes old mode, recomputes PID, turns heater back ON. Same race in `async_set_temperature`, `async_set_preset_mode`, `clear_integral`, PID-tuning service handlers.

**Fix:**
1. Reorder: set `_hvac_mode=OFF` BEFORE awaiting `_async_heater_turn_off`.
2. Wrap entire mutation block in `async with self._temp_lock` for mode/temp/preset/PID services.
3. Verify climate_control.py:41 OFF short-circuit triggers on stale call.

**Test:** Unit test: spawn `async_set_hvac_mode(OFF)` and `_async_control_heating` concurrently; assert heater ends OFF. Integration: rapid mode toggles do not strand heater ON.

**Risk:** Med — lock ordering wrong could deadlock with manager callbacks.

**Depends on:** none.

**Blocks:** H01, H03, A07.
