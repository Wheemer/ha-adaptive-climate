# Architectural 8: No PID NaN/Inf injection test harness

**File:** `tests/test_pid_controller.py` (new tests)

**Problem:** Many entry points accept floats without validation; no pinning test.

**Fix:**
1. Add `tests/test_pid_nan_safety.py`.
2. For each public entry point (`set_pid_param`, `set_gains`, `integral` setter, `decay_integral`, `scale_integral`, `set_feedforward`), assert NaN/Inf raise or are rejected.
3. Add fuzz-style test: random invalid inputs over 100 iterations.

**Test:** New test file passes; CI gate.

**Risk:** Low.

**Depends on:** H08, H09, H10 (validation must exist first).

**Blocks:** none.
