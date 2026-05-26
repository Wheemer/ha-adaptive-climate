# Low 09: Info-level logs in per-tick hot path

**File:** `managers/heater_controller.py` (various), `managers/cycle_tracker.py:790`

**Problem:** `_LOGGER.info("Refresh state ON ...")` non-state-change branches spam logs for multi-zone users.

**Fix:**
1. Demote info → debug on non-state-change branches.
2. Keep info for actual state transitions.

**Test:** Manual log check on idle zone — no per-tick info entries.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
