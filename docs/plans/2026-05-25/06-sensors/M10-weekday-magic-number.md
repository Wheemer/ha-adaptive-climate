# Medium 10: Sunday weekday=6 needs comment

**File:** `services/scheduled.py:437-438`

**Problem:** `weekday() != 6` correct for Sunday but easy to confuse with isoweekday()=7.

**Fix:**
1. Add `# datetime.weekday(): Mon=0..Sun=6` comment.
2. Or use named constant `SUNDAY_WEEKDAY = 6`.

**Test:** N/A.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
