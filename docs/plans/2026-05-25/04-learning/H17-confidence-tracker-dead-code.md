# High 17: `ConfidenceTracker.update_convergence_confidence` is dead code

**File:** `adaptive/confidence.py:107-183` vs `learning.py:1081-1224`

**Problem:** Tracker has full impl but `AdaptiveLearner.update_convergence_confidence` re-implements; tracker version reachable only via tests.

**Fix:**
1. Decide: delete tracker version OR delegate from learner.
2. Preferred: move weighted-learning logic into tracker; learner calls `tracker.update_convergence_confidence(...)` with cycle weight + metrics.
3. Update tests to exercise the single path.

**Test:** Unit + integration: behavior unchanged. Coverage shows no dead branches in tracker.

**Risk:** Med — large refactor touching hot path.

**Depends on:** none.

**Blocks:** C01 (clean split prerequisite).
