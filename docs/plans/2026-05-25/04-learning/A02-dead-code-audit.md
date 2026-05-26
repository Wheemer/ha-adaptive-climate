# Architectural 02: Establish dead-code detection coverage

**File:** multiple — `confidence.py`, `undershoot_detector.py`, `learning.py:get_previous_pid`, `cycle_weight` UNDERSHOOT branch

**Problem:** Several unreachable / unwired methods.

**Fix:**
1. Add coverage CI gate (e.g. ≥ 85% on `adaptive/`).
2. Add integration test exercising each public method end-to-end.
3. Use `vulture` to detect unused code.
4. Delete or wire identified dead paths (covered individually by H17, M05, L05, L20).

**Test:** CI fails when coverage drops below threshold; vulture in pre-commit.

**Risk:** Low — tooling.

**Depends on:** H17, M05, L05, L20.

**Blocks:** none.
