# Medium 24: Milestone notifications skipped on idle transitions

**File:** `managers/learning_milestone.py:64`

**Problem:** Skip when `new == 'idle' OR prev == 'idle'`. optimized→idle and idle→optimized both silent.

**Fix:**
1. Allow notifications across idle boundary at low priority.
2. Distinguish "entered idle (paused)" vs "resumed from idle".
3. Optional: add `last_non_idle_status` tracking so resume→optimized fires.

**Test:** Unit: optimized→idle→optimized → 2 notifications (pause + resume).

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Notification noise tradeoff?
