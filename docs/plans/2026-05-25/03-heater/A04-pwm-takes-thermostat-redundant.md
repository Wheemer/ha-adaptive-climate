# Architectural 04: PWMController takes thermostat directly — redundant coupling

**File:** `managers/pwm_controller.py:292-332`

**Problem:** PWM owned by HeaterController but takes thermostat reference.

**Fix:**
1. Replace thermostat ref with minimal callbacks/Protocol (`entity_id` str, optional `current_temp`/`target_temp` providers).
2. Update constructor and HeaterController wiring.

**Test:** Existing PWM tests pass with minimal mocks.

**Risk:** Med.

**Depends on:** A02 (same Protocol cleanup).

**Blocks:** none.
