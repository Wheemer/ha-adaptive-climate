# Low 19: Drift calc kp doesn't guard zero baseline

**File:** `adaptive/validation.py:362-388`

**Problem:** `_physics_baseline_kp` zero division: None-guarded but not zero-guarded (ki/kd are).

**Fix:**
1. Add `or self._physics_baseline_kp <= 0` to None check.
2. Mirror ki/kd pattern.

**Test:** Unit: baseline_kp=0 → drift returns None/0 cleanly.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
