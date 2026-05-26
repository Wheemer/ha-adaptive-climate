# High 02: Float equality compare on PID difference

**File:** `managers/heater_controller.py:1045`

**Problem:** `if abs(control_output) == self._difference:` is float-equality. Works today (`100.0 - 0.0`) but fragile for future float configs.

**Fix:**
1. Replace with `math.isclose(abs(control_output), self._difference, abs_tol=1e-6)` or `>= self._difference - 1e-6`.

**Test:** Unit test with `output_max=100.5, output_min=0.5, control_output=100.0` — assert max-output branch taken.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
