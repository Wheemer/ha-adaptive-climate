# Critical 01: HeatPipeline dead code / docs lie

**File:** `managers/heat_pipeline.py:1-82`, `managers/heater_controller.py:179-186`

**Problem:** `HeatPipeline` instantiated but never invoked. CLAUDE.md documents active "committed heat tracking" feature; implementation unreachable. `pwm_controller.calculate_adjusted_on_time` only adds delays, never consults pipeline.

**Fix (choose one):**
1. DELETE path: remove `heat_pipeline.py`, drop `_heat_pipeline` attr from `HeaterController`, strip "Committed heat tracking" section from CLAUDE.md + docs.
2. WIRE path: call `valve_opened()` from `HeaterController.async_turn_on`, `valve_closed()` from `async_turn_off`; query `committed_heat_remaining()` inside `PWMController.calculate_adjusted_on_time` and subtract from next cycle duty; thread through learning split overshoot into controllable vs committed.

**Test:** If WIRE — integration test that two back-to-back bursts under transport_delay see second burst shortened. If DELETE — confirm grep returns no references.

**Risk:** Med — DELETE simple but loses planned feature; WIRE touches PWM math (overshoot path).

**Depends on:** none.

**Blocks:** M05 (PWM transport_delay asymmetry — same area), A05 (HeatPipeline design model).

**Unresolved:** Product decision required — keep feature or kill it? See also `04-learning` if learning overshoot split is desired.
