# Medium 01: Performance deque overflows on relay chatter

**File:** `sensors/performance.py:122`

**Problem:** `maxlen=7200` (1 hr @ 1/s) overwhelmed by faulty relay firing 50/s. Oldest legitimate baseline drops, breaks "one state before window_start" invariant.

**Fix:**
1. Add chatter detection: drop state changes <1s after previous.
2. Log warning on chatter.

**Test:** Unit: feed 100/s for 60s; assert deque retains pre-chatter baseline.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
