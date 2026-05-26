# High 04: `_humidity_history` deque unbounded

**File:** `adaptive/humidity_detector.py:62, 78-85`

**Problem:** No `maxlen`; eviction by time only. High-frequency sensor inputs grow buffer until eviction; O(N) front scans.

**Fix:**
1. Compute reasonable cap: `maxlen = int(detection_window / min_expected_interval) + buffer` (e.g. 600).
2. `self._humidity_history = deque(maxlen=N)`.
3. Keep time-based eviction for staleness within bound.

**Test:** Unit: feed 10000 rapid readings → deque size capped, performance bounded.

**Risk:** Low.

**Depends on:** none.

**Blocks:** H03.
