# Low 04: Force recreation of trackers instead of `reset()`

**File:** `adaptive/learning.py:917, 921-923`

**Problem:** `ConfidenceContributionTracker` / `HeatingRateLearner` reset by re-instantiating with heating_type — easy to forget.

**Fix:**
1. Add `reset()` method to both classes; preserve config (heating_type).
2. Replace recreation with `tracker.reset()`.

**Test:** Unit: reset → state cleared, config preserved.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
