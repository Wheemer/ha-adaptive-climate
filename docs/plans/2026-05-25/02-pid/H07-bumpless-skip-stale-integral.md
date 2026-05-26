# High 7: Bumpless skip leaves stale integral from before OFF

**File:** `pid_controller/__init__.py:354,360`

**Problem:** Large-error / setpoint-change skip path sets `_last_output_before_off = None` but leaves stale pre-OFF integral. After long OFF thermal state diverged → first calc applies 100% from stale integral.

**Fix:**
1. When bumpless conditions fail, also `self._integral = 0.0` (or scale by OFF-duration decay).
2. Decay formula: `integral *= max(0.1, exp(-off_seconds / tau))` where tau ~ thermal_time_constant.
3. Document reset in skip branches.

**Test:** Unit: OFF for 1h with prior integral=80, resume with large error, assert integral reset.

**Risk:** Med. Could slow recovery in some scenarios; pair with bumpless tests.

**Depends on:** C02.

**Blocks:** none.
