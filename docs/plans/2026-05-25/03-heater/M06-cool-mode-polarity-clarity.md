# Medium 06: COOL mode control_output polarity convention unclear

**File:** `managers/pwm_controller.py:233-237, 254, 261`

**Problem:** `no_demand` check tests sign of `control_output` differently than magnitude logic below (which uses `abs(...)`). Convention for COOL mode polarity not documented.

**Fix:**
1. Document module-level convention (likely: positive = demand in both modes).
2. Add inline comment at no_demand check explaining sign vs magnitude usage.
3. Add unit test asserting COOL mode with `control_output = -50` behaves as expected (positive demand).

**Test:** Unit test COOL mode demand sign/magnitude.

**Risk:** Low — clarification, may surface latent bug if convention is inconsistent.

**Depends on:** none.

**Blocks:** none.
