# Architectural 01: Extract `LearningCoordinator` from `AdaptiveLearner` god-class

**File:** `adaptive/learning.py` (1701 lines, 30+ methods)

**Problem:** Owns confidence + validation + undershoot + contribution + heating-rate + rule state + 20+ aliases.

**Fix:**
1. Define `LearningCoordinator` (≤300 lines) composing managers.
2. Move per-mode state into a `LearningState(mode)` dataclass.
3. Public API: `process_cycle(metrics, mode)`, `get_status(mode)`, `get_recommendations(mode)`.
4. `AdaptiveLearner` becomes thin facade for backward compat (or eliminate).
5. Per-mode managers (one per HEAT/COOL) where data is mode-specific.

**Test:** Existing public API tests pass; new unit tests per manager in isolation.

**Risk:** High — major refactor.

**Depends on:** C01 (file split), L01 (alias cleanup), H17 (dead code).

**Blocks:** A04, A05.
