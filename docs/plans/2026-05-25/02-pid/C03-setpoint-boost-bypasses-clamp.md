# Critical 3: Setpoint boost mutates `_integral` bypassing clamp

**File:** `managers/setpoint_boost.py:150,162`

**Problem:** `_apply_boost` does `self._pid.integral += boost` / `*= decay`. Clamp `[out_min - E - F, out_max - E - F]` only runs inside `calc()` `dt >= 5s` branch. Freeze branch / first-call branch leaves integral unconstrained → windup beyond back-calc recovery.

**Fix:**
1. Add `PIDController.boost_integral(amount)` and `scale_integral_clamped(factor)` that re-clamp.
2. Replace direct `integral +=` / `*=` in setpoint_boost with these methods.
3. Move clamp logic to top of `calc()` (run regardless of dt branch).
4. Same for `decay_integral`, `scale_integral` (see H10).

**Test:** Unit: boost when integral already at `out_max - E - F`, assert clamp holds. Integration: setpoint_boost tests pass.

**Risk:** Med. Clamp on every calc may surface latent edge cases.

**Depends on:** none.

**Blocks:** M31, H10, A01 (IntegralManager).
