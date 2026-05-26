# Critical 01: Split `adaptive/learning.py` (1701 lines, >2x 800-line limit)

**File:** `adaptive/learning.py:1700`

**Problem:** File more than 2x CLAUDE.md max. God-class `AdaptiveLearner` owns confidence + validation + undershoot + contribution + heating-rate + serialization wiring + 120-line block of backward-compat aliases.

**Fix:**
1. Extract backward-compat property aliases (lines 224–350) to `learning_compat.py` mixin, or delete after test refactor (see L01).
2. Extract `_check_*` / averaging math (~200 lines) to `learning_metrics.py`.
3. Extract undershoot wiring (~100 lines around 1418-1500) to `learning_undershoot.py`.
4. Extract serialization wiring (~100 lines around 1627-1656) to thin facade calling `learner_serialization`.
5. Keep `AdaptiveLearner` spine ≤400 lines; only orchestration of composed managers.

**Test:** Existing tests pass unchanged. Pyright strict clean. Module imports unchanged externally.

**Risk:** High — large refactor of core learning. Many call sites reach into private attrs.

**Depends on:** C05, C06, C09, H17 (fix correctness bugs first, refactor second).

**Blocks:** A01 (LearningCoordinator extraction).
