# High 06: PWMController writes private _has_demand on HeaterController

**File:** `managers/pwm_controller.py:341`

**Problem:** `heater_controller._has_demand = True` crosses API boundary into private attr from delegate module.

**Fix:**
1. Add public method `HeaterController.mark_pulse_demand(active: bool)`.
2. Replace direct attribute write in PWMController with method call.
3. Optionally add setter validation (idempotency log if state unchanged).

**Test:** Existing PWM tests pass; grep confirms no remaining cross-module private writes.

**Risk:** Low — mechanical refactor.

**Depends on:** H01 (file split may relocate the attribute).

**Blocks:** A03 (broader cross-module private access cleanup).
