# Medium 10: mixed falsy + `is not None` checks rejecting valid 0 values

**File:** `custom_components/adaptive_climate/climate.py:1381`

**Problem:** `if start_temp and end_temp and duration_minutes and outdoor_temp is not None:` — target 0°C, 0min, 0°C outdoor all valid but treated as missing.

**Fix:**
1. Replace all with `is not None` checks: `if start_temp is not None and end_temp is not None and ...`.

**Test:** Unit: 0.0°C values pass through.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
