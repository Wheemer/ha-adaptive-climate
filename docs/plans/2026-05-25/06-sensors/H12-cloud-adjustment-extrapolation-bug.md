# High 12: Cloud adjustment 10x overshoot when extrapolating clearer than learned

**File:** `solar/solar_gain.py:217-242`

**Problem:** `actual_factor / learned_factor` produces 10x when learned=OVERCAST(0.1) and actual=CLEAR(1.0). Can't back-extrapolate baseline from cloud-only data.

**Fix:**
1. Skip pattern if actual cloud factor > 2× learned (insufficient data).
2. Cap adjustment factor at 3.0× to prevent runaway.
3. Prefer patterns learned under clearer conditions.

**Test:** Unit: pattern learned at OVERCAST, query at CLEAR; assert adjustment skipped or capped.

**Risk:** Low.

**Depends on:** H11.

**Blocks:** none.
