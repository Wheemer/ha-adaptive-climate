# Medium 12: `get_adaptive_learner` closure re-resolves coordinator each call

**File:** `custom_components/adaptive_climate/climate_init.py:166-173`

**Problem:** Closure re-resolves coordinator/zone_data per call; inconsistent with cached `_coordinator` pattern.

**Fix:**
1. Cache `adaptive_learner` on first successful resolve.
2. Fall back to fresh lookup only on cache miss.
3. Or refactor to a method on a class with cached state.

**Test:** Unit: repeated calls return same instance after first resolve.

**Risk:** Low.

**Depends on:** H06.

**Blocks:** none.
