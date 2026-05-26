# Arch 01: NightSetbackManager reaches into `_calculator._get_target_temp()`

**File:** `managers/night_setback_manager.py:249, 295, 356, 374`

**Problem:** Manager accesses calculator's private method. Violates encapsulation.

**Fix:**
1. Expose `get_target_temp()` publicly on calculator.
2. Or have manager hold own `get_target_temp` callback (already accessible at construction).
3. Update all four call sites.

**Test:** Existing tests pass.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
