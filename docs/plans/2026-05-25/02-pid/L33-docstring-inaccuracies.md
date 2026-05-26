# Low 33: Docstring inaccuracies

**File:** `pid_controller/__init__.py:50`, `managers/setpoint_boost.py:124`

**Problem:** Ke docstring lacks typical magnitude; setpoint_boost `_now` docstring incorrect.

**Fix:**
1. PID ke docstring: add "typical 0.01-0.05 °C output / °C dext".
2. setpoint_boost: rename `_now` -> `_scheduled_at` and document as scheduled fire time.

**Test:** Visual review.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
