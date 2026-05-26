# Medium 05: `_saved_target_temp` uses `or` (falsy-0 treated as missing)

**File:** `custom_components/adaptive_climate/climate.py:106`

**Problem:** `kwargs.get("target_temp") or kwargs.get("away_temp")` — 0.0°C treated as missing.

**Fix:**
1. Replace with explicit: `target_temp if target_temp is not None else away_temp`.

**Test:** Unit: target_temp=0.0 retained.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
