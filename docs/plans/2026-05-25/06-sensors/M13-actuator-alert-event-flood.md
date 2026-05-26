# Medium 13: Actuator maintenance alert fires per state change

**File:** `sensors/actuator_wear.py:163-179`

**Problem:** Event fires on every climate state change once threshold crossed. Hundreds/hour possible.

**Fix:**
1. Track `_last_alert_at`; rate-limit to 1/hour.
2. Or fire only on level transitions (warn→critical).

**Test:** Unit: 100 changes in 10min; assert ≤1 event.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
