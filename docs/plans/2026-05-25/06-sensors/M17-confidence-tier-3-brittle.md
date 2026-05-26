# Medium 17: CONFIDENCE_TIER_3 >100 silently breaks "optimized"

**File:** `state_attributes.py:172-179`

**Problem:** `tier_3 / 100.0` becomes >1.0 if const bumped, no status reaches "optimized".

**Fix:**
1. Clamp tier_3 to ≤100 at module load; raise ValueError if exceeded.
2. Add inline `if CONFIDENCE_TIER_3 > 100: raise ValueError(...)`.

**Test:** Unit: monkeypatch >100; assert ValueError.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
