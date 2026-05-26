# Medium 03: sync `set_hvac_mode` diverges from async version

**File:** `custom_components/adaptive_climate/climate.py:1077-1100`

**Problem:** Sync version skips integral reset on HEAT↔COOL, no mode-sync, no ModeChangedEvent. If HA invokes sync (state restoration/lovelace), state becomes inconsistent.

**Fix:**
1. Extract shared core `_apply_hvac_mode_change(mode)` (sync, mutation-only).
2. Sync wrapper calls core + schedules async followups via `hass.async_create_task`.
3. Async wrapper does the same with awaits.
4. Or remove sync override entirely (let HA default convert to async).

**Test:** Unit: sync call results in same final state as async call.

**Risk:** Med — touches core mode logic.

**Depends on:** C01, H11.

**Blocks:** none.
