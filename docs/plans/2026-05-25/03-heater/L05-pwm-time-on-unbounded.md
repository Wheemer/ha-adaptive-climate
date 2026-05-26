# Low 05: PWM time_on may exceed _pwm after min-off-time adjustment

**File:** `managers/pwm_controller.py:398-401`

**Problem:** `time_on *= self._min_closed_time / time_off` can overshoot `_pwm` in edge cases.

**Fix:**
1. Add `time_on = min(time_on, self._pwm - self._min_closed_time)` after the multiplication.

**Test:** Unit test extreme small `time_off` — assert `time_on` bounded.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
