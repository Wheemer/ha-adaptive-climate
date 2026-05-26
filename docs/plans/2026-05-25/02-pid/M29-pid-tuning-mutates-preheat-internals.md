# Medium 29: `pid_tuning.py` mutates preheat learner private state

**File:** `managers/pid_tuning.py:471-472`

**Problem:** `preheat_learner._observations.clear()` and `_add_observation_counter = 0` reach into other module's internals.

**Fix:**
1. Add `PreheatLearner.clear_observations()` method (resets `_observations` + counter).
2. Replace direct mutations with method call.

**Test:** Unit: call clear_observations, assert state reset.

**Risk:** Low.

**Depends on:** M28.

**Blocks:** none.
