# Medium 19: Per-bin list overflow uses O(N) slice

**File:** `adaptive/heating_rate_learner.py:160-161`; `adaptive/preheat.py:160-162`

**Problem:** `self._bins[bin_key] = self._bins[bin_key][-MAX:]` copies list each overflow.

**Fix:**
1. Change bin storage from `list` to `deque(maxlen=MAX)`.
2. Update from_dict/to_dict to handle deque.
3. Update read sites if any assume list (most use iteration — safe).

**Test:** Unit: append > MAX → deque size = MAX, no list copy.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
