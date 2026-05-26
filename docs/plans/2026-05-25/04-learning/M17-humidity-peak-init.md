# Medium 17: Humidity peak ratchets from first reading only

**File:** `adaptive/humidity_detector.py:115-117`

**Problem:** `_peak_humidity` initialized to first paused reading; spike captured before pause is lost.

**Fix:**
1. On entering paused, initialize peak to `max(history)` (history contains pre-pause readings).
2. Then continue ratcheting upward.

**Test:** Unit: pre-pause buffer has 80% → pause entered at 75% → peak set to 80%.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
