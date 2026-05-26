# High 14: set_hvac_mode receives "unavailable" string on restore

**File:** `state_restorer.py:99-100`

**Problem:** `set_hvac_mode(old_state.state)` passes raw string. `"unavailable"` (entity offline at shutdown) hits setter expecting HVACMode enum → raises or no-ops.

**Fix:**
1. Validate `old_state.state in HVACMode.__members__` before call.
2. Fallback to `HVACMode.OFF` or previously-known mode.
3. Log if invalid.

**Test:** Unit: restore with state=`"unavailable"`, `"unknown"`, `"heat"`; assert safe fallback or correct mode.

**Risk:** Low. Cross-ref: `01-climate/H06` likely overlaps.

**Depends on:** none.

**Blocks:** none.
