# Medium 05: PWM transport_delay added but not symmetrically subtracted

**File:** `managers/pwm_controller.py:148-181, 410`

**Problem:** `calculate_adjusted_on_time` adds `transport_delay + valve_actuation_time`. Off-check uses `time_to_close = time_on - close_command_offset` where offset = `valve_actuation_time/2`. Net open = `transport_delay + valve_actuation_time/2 + max(heat, min_open)` — no symmetric `transport_delay/2` cancels added delay → overshoot ≈ one full transport_delay each burst.

**Fix:**
1. Audit intended timing: should transport_delay also have a half-offset on close?
2. If yes: `time_to_close = time_on - close_command_offset - transport_delay/2`.
3. If no: document that transport_delay is purely additive (post-valve heat tail).
4. Add unit test asserting net open duration matches design intent for floor_hydronic.

**Test:** Unit test floor_hydronic burst — assert net on-time matches model; integration regression on overshoot reduction.

**Risk:** Med — affects cycle duty directly; verify against C01 if HeatPipeline gets wired.

**Depends on:** C01 (HeatPipeline decision changes the math).

**Blocks:** none.

**Unresolved:** Confirm intent with HVAC expert — is transport_delay symmetric or post-valve only?
