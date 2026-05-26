# Low 36: Clock-jumped dt logged but no metric exposed

**File:** `managers/control_output.py:153`

**Problem:** No observability for sleep/resume diagnostics.

**Fix:**
1. Add `_clock_jumps_detected: int = 0` instance attribute (after M27).
2. Increment on each clamp.
3. Expose in debug state attributes (`debug.control.clock_jumps`).

**Test:** Unit: trigger 3 jumps, assert counter == 3 in attributes.

**Risk:** Low.

**Depends on:** M27, H11.

**Blocks:** none.
