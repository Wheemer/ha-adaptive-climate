# Medium 17: `_is_high_solar_gain` reads orientation per zone per call

**File:** `coordinator.py:377-432`

**Problem:** Hot-path helper reading zone_data each call. Hardcoded "elevation > 15" not extracted.

**Fix:**
1. Cache `_zone_orientations: dict[str, str]` populated at zone register/unregister.
2. Extract `SOLAR_ELEVATION_MIN = 15.0` constant.
3. Update docstring to match.

**Test:** Unit: register zones with orientations, assert cache populated. Unregister, assert removed.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
