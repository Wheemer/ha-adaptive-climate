# Medium 14: `valve_actuation_config` int|float union

**File:** `custom_components/adaptive_climate/climate_setup.py:328-332`

**Problem:** `valve_actuation_config.total_seconds()` float; `HEATING_TYPE_VALVE_DEFAULTS.get(..., 0)` int. Silent union.

**Fix:**
1. Cast: `int(valve_actuation_config.total_seconds())` before storage.
2. Type annotation: `valve_actuation_time: int` on entity.

**Test:** Pyright clean; existing tests pass.

**Risk:** Low.

**Depends on:** C02.

**Blocks:** none.
