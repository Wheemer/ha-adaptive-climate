# Low 23: `FLOOR_THICKNESS_LIMITS[layer_type]` may KeyError

**File:** `adaptive/floor_physics.py:97`

**Problem:** Valid layer_type missing from const dict → KeyError.

**Fix:**
1. `min_thickness, max_thickness = FLOOR_THICKNESS_LIMITS.get(layer_type, (0, 1000))`.
2. Or add const-side test asserting keys cover all valid layer_types.

**Test:** Unit: missing key → defaults used, no crash.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
