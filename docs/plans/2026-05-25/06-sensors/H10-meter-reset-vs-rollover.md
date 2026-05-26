# High 10: Meter-reset detection misclassifies rollover

**File:** `sensors/energy.py:553-564`

**Problem:** `current < week_start` treated as reset. 6-digit utility meter rolling over from 999999→0 misclassified, week-to-date consumption lost.

**Fix:**
1. Track `last_meter_reading` (already at line 391).
2. Treat as reset only if `current < last_meter_reading` (drop within week), not just `< week_start`.
3. On rollover, compute delta as `(max_value - last) + current` if `max_value` configurable, else accept rollover and log.

**Test:** Unit: simulate rollover sequence; assert week_total accumulates correctly.

**Risk:** Med.

**Depends on:** C07.

**Blocks:** none.
