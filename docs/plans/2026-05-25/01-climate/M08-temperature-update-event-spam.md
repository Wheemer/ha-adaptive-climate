# Medium 08: TemperatureUpdateEvent emitted every control-loop call

**File:** `custom_components/adaptive_climate/climate_control.py:118-128`

**Problem:** Event emitted unconditionally when temps non-None, even unchanged. Spams subscribers at sub-60s intervals.

**Fix:**
1. Track last emitted (temp, setpoint).
2. Emit only on actual change (compare with small epsilon e.g. 0.01).

**Test:** Unit: identical consecutive updates → single emit.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
