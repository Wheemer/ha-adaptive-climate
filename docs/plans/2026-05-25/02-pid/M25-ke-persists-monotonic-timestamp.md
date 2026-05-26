# Medium 25: `KeManager._steady_state_start` is monotonic, persisted across restarts

**File:** `managers/ke_manager.py:233-241,365-377`

**Problem:** Monotonic clock resets per process. Persisted value is meaningless after restart; steady-state-duration check broken indefinitely after every restart.

**Fix:**
1. Don't persist `_steady_state_start` — reset to None on restore.
2. Or switch to `dt_util.utcnow()` and convert at compare site.
3. Prefer option 1: thermal state unknown after restart.
4. Audit other monotonic-persisted timestamps (see 04 stream for UndershootDetector parallel).

**Test:** Unit: persist, restart, assert steady-state check starts fresh.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none. Related to `04-learning/<undershoot-detector-timestamp>`.
