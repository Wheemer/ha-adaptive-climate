# High 01: Forced resume doesn't clear `_stabilization_start`

**File:** `adaptive/humidity_detector.py:102-112`

**Problem:** Forced resume from paused clears `_peak_humidity` and `_pause_start` but leaves `_stabilization_start`. Prior spike→drop→re-spike can make next stabilizing think delay already elapsed.

**Fix:**
1. In forced resume branch, set `self._stabilization_start = None`.
2. Add same reset on any state→NORMAL transition (DRY: `_reset_to_normal()`).

**Test:** Unit: spike→drop→stabilizing→re-spike→forced resume→next stabilizing waits full delay.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
