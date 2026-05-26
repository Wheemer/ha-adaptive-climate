# Medium 28: `pid_tuning.py` reaches into `_ke_controller` / `_preheat_learner` via getattr

**File:** `managers/pid_tuning.py:437,463,469`

**Problem:** Not declared on Protocol; bypasses type check. Violates "managers receive Protocol" rule.

**Fix:**
1. Add `ke_controller: KeManager | None` and `preheat_learner: PreheatLearner | None` to `PIDTuningState` Protocol (or inject as constructor args).
2. Replace `getattr(self._state, "_ke_controller", None)` with `self._state.ke_controller`.
3. Same for `_preheat_learner`.

**Test:** Pyright clean; existing tests pass.

**Risk:** Low.

**Depends on:** none.

**Blocks:** M29, A02.
