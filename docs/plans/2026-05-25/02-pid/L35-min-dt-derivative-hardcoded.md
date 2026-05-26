# Low 35: `MIN_DT_FOR_DERIVATIVE = 5.0` hard-coded

**File:** `pid_controller/__init__.py:30`

**Problem:** 5s lower bound disables derivative on forced-air with 1s sensors.

**Fix:**
1. Add `min_dt_for_derivative` param to PID `__init__` (default 5.0).
2. Map per `HeatingType`: floor=10, radiator=5, convector=3, forced_air=1.
3. Pass from `climate_init.py` based on `heating_type`.

**Test:** Unit: forced_air with 1s sensor, assert derivative branch fires.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
