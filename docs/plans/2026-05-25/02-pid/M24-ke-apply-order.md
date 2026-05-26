# Medium 24: `apply_adaptive_ke` mutates learner before persisting gains

**File:** `managers/ke_manager.py:348-355`

**Problem:** `ke_learner.apply_ke_adjustment(recommendation)` runs before `_gains_manager.set_gains`. If set_gains raises (post-H09), learner state is already mutated.

**Fix:**
1. Reorder: call `set_gains` first.
2. Only update `ke_learner._current_ke` after set_gains succeeds.
3. Wrap in try/except; on set_gains failure, log and bail without mutating learner.

**Test:** Unit: force set_gains to raise, assert ke_learner._current_ke unchanged.

**Risk:** Low.

**Depends on:** H09.

**Blocks:** none.
