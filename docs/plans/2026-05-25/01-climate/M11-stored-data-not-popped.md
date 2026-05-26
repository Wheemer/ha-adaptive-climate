# Medium 11: `stored_preheat_data`/`stored_ke_data` never popped after restoration

**File:** `custom_components/adaptive_climate/climate_init.py:104-139`

**Problem:** Read but not popped from `coordinator.zone_data`. Duplicate state persists forever.

**Fix:**
1. After successful restoration, `zone_data.pop("stored_preheat_data", None)` and `pop("stored_ke_data", None)`.

**Test:** Unit: after init, keys absent from zone_data.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
