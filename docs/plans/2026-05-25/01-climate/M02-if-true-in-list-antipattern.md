# Medium 02: `if True in [temp is not None ...]` anti-pattern

**File:** `custom_components/adaptive_climate/climate.py:146-157`

**Problem:** Awkward `if True in [temp is not None for temp in [...]]`.

**Fix:**
1. Replace with `if any(temp is not None for temp in (...))`.

**Test:** Existing tests pass.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
