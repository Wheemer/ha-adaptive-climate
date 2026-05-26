# High 03: learning_gate patched with private night_setback_controller post-construction

**File:** `custom_components/adaptive_climate/climate_init.py:199`

**Problem:** `learning_gate._night_setback_controller = thermostat._night_setback_controller` patches private attribute to break constructor cycle.

**Fix:**
1. Add public `NightSetbackLearningGate.set_night_setback_controller(controller)` (mirror StatusManager pattern at climate.py:478).
2. Replace patch with method call.
3. Or reorder construction: build gate after night_setback_controller.

**Test:** Unit: gate.set_night_setback_controller assigns; subsequent gate behavior unchanged.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
