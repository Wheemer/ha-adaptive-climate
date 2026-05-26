# Low 08: Inline `dt_util` imports in `heating_rate_learner`

**File:** `adaptive/heating_rate_learner.py:124-146` (and start/end_session)

**Problem:** `from homeassistant.util import dt as dt_util` inside methods.

**Fix:**
1. Hoist to module top.
2. Verify no circular import.

**Test:** Lint passes; existing tests pass.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
