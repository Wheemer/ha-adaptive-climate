# Low 08: Redundant `auto_mode_switching_enabled = True` attribute

**File:** `managers/auto_mode_switching.py:281`

**Problem:** Manager only instantiated when enabled; attribute redundant.

**Fix:**
1. Drop the assignment.

**Test:** State attribute consumers don't break.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
