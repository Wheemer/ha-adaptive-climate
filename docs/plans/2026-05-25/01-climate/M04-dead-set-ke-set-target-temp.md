# Medium 04: `_set_ke` dead; `_set_target_temp` mixes logic and mutation

**File:** `custom_components/adaptive_climate/climate.py:1684-1687,1744-1770`

**Problem:** `_set_ke` documented as legacy `pass`. `_set_target_temp` has side-effects mixed with state mutation.

**Fix:**
1. Delete `_set_ke`; remove from any callback registrations.
2. Route `_set_target_temp` logic entirely through TemperatureManager events.
3. Keep entity-level setter as thin pass-through or remove if redundant.

**Test:** Setpoint changes still propagate; existing tests pass.

**Risk:** Low-Med.

**Depends on:** none.

**Blocks:** A03.
