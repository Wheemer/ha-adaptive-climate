# Medium 18: Zero-duration treated as "stalled rate 0"

**File:** `adaptive/heating_rate_learner.py:268-282`

**Problem:** Safety `0.0` rate enters `< MIN_OBSERVATION_RATE` reject path, but duration==0 is clock anomaly, not real stall.

**Fix:**
1. Early return BEFORE rate computation: `if duration_hours <= 0: return  # skip, not stall`.
2. Log DEBUG with reason "zero duration".

**Test:** Unit: duration=0 → skipped without rejection log.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
