# Low 03: heater_entity_id list silently uses [0]

**File:** `sensors/performance.py:151-157`

**Problem:** Defensive list-or-string handling, but silently picks `[0]` if list >1.

**Fix:**
1. Log warning when list has >1 entries.

**Test:** Unit: pass list of 2; assert warning logged.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
