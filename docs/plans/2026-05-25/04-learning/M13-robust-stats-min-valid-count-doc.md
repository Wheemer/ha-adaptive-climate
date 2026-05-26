# Medium 13: `robust_average` returns empty outliers when skipped

**File:** `adaptive/robust_stats.py:148-150` + caller `adaptive/learning.py:684-735`

**Problem:** When N < min_valid_count, returns median + `[]` outliers. Caller logs "0 outliers" misleadingly.

**Fix:**
1. Return `(median, None)` for outliers when detection skipped.
2. Caller distinguishes None (skipped) vs `[]` (none detected).
3. Update log to "outlier detection skipped (insufficient N)".

**Test:** Unit: N=2 → outliers is None, log clear.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
