# High 08: _outdoor_temp_history list unbounded

**File:** `managers/cycle_tracker.py:121-122`

**Problem:** Plain list with no cap (vs `_temperature_history` deque). Long settling windows grow unbounded.

**Fix:**
1. Convert to `deque(maxlen=N)` matching temperature_history capacity (or smaller — outdoor sampling slower).
2. If capping affects downstream use, capture `_cycle_start_outdoor_temp` similar to H07.

**Test:** Long-run test asserts bounded memory; metrics using outdoor history unaffected.

**Risk:** Low.

**Depends on:** H07 (same pattern).

**Blocks:** none.
