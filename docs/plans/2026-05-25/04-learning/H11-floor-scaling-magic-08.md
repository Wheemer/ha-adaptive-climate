# High 11: Hard-coded `0.8` floor scaling approx wrong for non-floor types

**File:** `adaptive/learning.py:1100-1107, 1151-1163`

**Problem:** `is_stable = current_confidence >= (tier1_base * 0.8)` duplicated; 0.8 correct only for floor_hydronic. Radiator (0.9), convector (1.0), forced_air (1.1) get wrong threshold.

**Fix:**
1. Replace inline `0.8` with call to `confidence._get_scaled_tier(1, heating_type)` or equivalent helper.
2. Inject real scaled tier-1 from `HEATING_TYPE_CONFIDENCE_SCALE` via tracker method.
3. Remove duplication (single helper).

**Test:** Unit: assert `is_stable` threshold matches scaled tier per heating type.

**Risk:** Low.

**Depends on:** none.

**Blocks:** A07 (magic-number cleanup).
