# Medium 26: `ControlOutputManager` compares `HVACMode` to raw string

**File:** `managers/control_output.py:450,472`

**Problem:** `_hvac_mode != "heat"` compares enum to string. Works (enum == str-value) but violates CLAUDE.md "never raw strings".

**Fix:**
1. Replace `"heat"` with `HVACMode.HEAT`, `"cool"` with `HVACMode.COOL`.
2. Add import at top.
3. Grep for other raw string mode compares in same file.

**Test:** Existing tests pass; pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
