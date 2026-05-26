# High 09: `is_stalled` false-positive on fresh session

**File:** `adaptive/heating_rate_learner.py:331-332`

**Problem:** `last_progress_cycle = 0` + `cycles_in_session` increments per cycle → 3 slow cycles without rise threshold cross flags stall on first session.

**Fix:**
1. Init `last_progress_cycle = cycles_in_session` once a temp is observed at session start.
2. Or: require min `cycles_in_session >= STALL_CYCLES + 1` before stall returns true.

**Test:** Unit: fresh session, 3 slow cycles → `is_stalled() == False`; 6 slow cycles → True.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
