# Medium 09: Comfort score deviation formula not heating-type-aware

**File:** `sensors/comfort.py:232`

**Problem:** Hardcoded "0°C=100, 2°C=0" linear. Too lenient for floor_hydronic (0.5°C tol), too strict for forced_air (0.15°C).

**Fix:**
1. Scale denominator by heating type convergence threshold.
2. Pull threshold from existing HEATING_TYPE config.

**Test:** Unit: floor_hydronic + 0.4°C dev → moderate; forced_air + 0.4°C → near zero.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
