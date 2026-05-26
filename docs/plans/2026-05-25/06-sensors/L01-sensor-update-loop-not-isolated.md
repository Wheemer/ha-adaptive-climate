# Low 01: One sensor exception aborts whole update loop

**File:** `sensor.py:158-162`

**Problem:** `async_update_sensors` runs sensors in series; one raise aborts rest.

**Fix:**
1. Wrap each `await sensor.async_update()` + `async_write_ha_state()` in try/except with log.

**Test:** Unit: mock sensor that raises; assert others still update.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
