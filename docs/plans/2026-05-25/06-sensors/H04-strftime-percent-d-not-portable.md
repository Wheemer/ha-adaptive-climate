# High 04: `%-d` strftime flag not portable

**File:** `services/scheduled.py:191` (and `analytics/reports.py:195-196`)

**Problem:** `%-d` only works on glibc/macOS. Windows/musl raises ValueError.

**Fix:**
1. Replace `strftime("%b %-d")` with `f"{start_date:%b} {start_date.day}"`.
2. Grep repo for all `%-d`/`%-m`/`%-H` usages and replace.

**Test:** Unit: format on Windows-equivalent locale; assert no exception.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
