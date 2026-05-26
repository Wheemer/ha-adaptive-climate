# Medium 02: Inconsistent robust_average usage

**File:** `adaptive/learning.py:752-757`

**Problem:** `avg_inter_cycle_drift` and `avg_settling_mae` use `sum/len` while others use `robust_average`. Same window, same outlier concerns.

**Fix:**
1. Replace `sum/len` with `robust_average(values)` for both.
2. Use returned avg (ignore outliers list or log count).

**Test:** Unit: outlier in drift values doesn't dominate avg.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
