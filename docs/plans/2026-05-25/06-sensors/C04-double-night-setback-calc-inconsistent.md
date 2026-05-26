# Critical 04: Double night-setback calc returns inconsistent results

**File:** `managers/state_attributes.py:772` (also line 734)

**Problem:** `_calculate_night_setback_adjustment()` invoked twice per attribute read; uses `dt_util.utcnow()` internally so straddling a boundary yields different `in_night`/`info` between calls → inconsistent override entry.

**Fix:**
1. Call once at top of `_build_status_attribute`, cache as local.
2. Pass result to both consumers (override builder + cooling clamp branch).
3. Remove duplicate call.

**Test:** Unit: mock time across setback boundary; assert single consistent result used in both consumers.

**Risk:** Low.

**Depends on:** C03 (same function).

**Blocks:** none.
