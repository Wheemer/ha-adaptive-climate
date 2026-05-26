# Critical 02: valve_actuation_time / transport_delay unit mismatch

**File:** `climate_setup.py:332`, `climate.py:332`, `climate_init.py:98`, `climate.py:1859`, `climate_control.py:344`

**Problem:** `valve_actuation_time` stored as float seconds; `_effective_min_on_seconds` adds `int(self._transport_delay * 60)`. `climate.py:1859` calls `pid_controller.set_transport_delay(delay)` with MINUTES from `coordinator.get_transport_delay_for_zone`. `climate_control.py:344` calls `heater_controller.set_transport_delay(transport_delay_minutes * 60)` SECONDS. Two callers, two units, same-looking setters.

**Fix:**
1. Audit `get_transport_delay_for_zone` docstring + actual return unit.
2. Standardize: all `set_transport_delay` accept SECONDS. Rename or add type hint with unit suffix (e.g. `_seconds`).
3. Fix `climate.py:1859` to multiply ×60.
4. Add unit-suffix convention to const.py constants.

**Test:** Unit: assert PID and heater see identical transport_delay value (seconds) for the same manifold. Integration: zone with manifold delay 2.0min → both controllers receive 120.

**Risk:** Med — fixing units could expose latent bugs in PID feedforward timing.

**Depends on:** C03 (manifold lookup must work first to test).

**Blocks:** M11, A06.
