# Low 38: `pid_tuning.py:324` mutates `adaptive_learner._auto_apply_count` directly

**File:** `managers/pid_tuning.py:324`

**Problem:** Private attribute mutation across module boundary. Also related to `04-learning/C13` (mode-confused counter).

**Fix:**
1. Add `AdaptiveLearner.increment_auto_apply_count(mode)` method.
2. Replace direct mutation.
3. Coordinate with 04-learning fix for mode-aware counter.

**Test:** Unit: call increment, assert count++. Pairs with 04 fix.

**Risk:** Low.

**Depends on:** none. Coordinate with `04-learning/C13`.

**Blocks:** none.
