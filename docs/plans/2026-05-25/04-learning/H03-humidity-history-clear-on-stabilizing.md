# High 03: Stabilizing→spike requires 2 new readings

**File:** `adaptive/humidity_detector.py:130-131`

**Problem:** On exit to stabilizing, `_humidity_history.clear()` + appends current. Re-spike during stabilizing needs 2 readings before rate fires; HA on-change sensors may take minutes.

**Fix:**
1. Keep last 1-2 readings instead of clearing: `self._humidity_history = deque([last], maxlen=N)`.
2. Or: add absolute-single-sample rate check (spike vs last reading) as fallback.

**Test:** Unit: stabilizing → single high reading triggers re-pause.

**Risk:** Low.

**Depends on:** H04 (deque maxlen).

**Blocks:** none.
