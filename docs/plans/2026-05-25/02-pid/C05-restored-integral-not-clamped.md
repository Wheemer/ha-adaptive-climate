# Critical 5: Restored integral not clamped against current bounds

**File:** `managers/state_restorer.py:132`

**Problem:** `_pid_controller.integral = thermostat._i` writes raw float without clamp. If `out_max`/`Ke`/`F` changed across restart, integral violates `[out_min - E - F, out_max - E - F]`. First calc has `dt=0` so clamp skipped; oversized integral persists until first `dt>=5s` calc.

**Fix:**
1. After setter assignment, call new `PIDController.clamp_integral()` method.
2. Pass current `external` and `feedforward` for bound calc.
3. Alternative: rely on C03 fix (always clamp at top of `calc()`).

**Test:** Unit: persist integral=100, restore with out_max=50, assert clamped to bound.

**Risk:** Low. Defensive write.

**Depends on:** C03 (shared clamp logic).

**Blocks:** none.
