# Medium 14: MAD=0 with outliers present silently passes

**File:** `adaptive/robust_stats.py:105-107`

**Problem:** MAD=0 when 51%+ identical (e.g. nine 0s, one 100). Returns no outliers despite obvious 100.

**Fix:**
1. When `mad == 0` AND `max(values) - min(values) > epsilon`, fall back to IQR or stdev-based detection.
2. Helper `_fallback_outliers(values)` using stdev rule (>3σ).

**Test:** Unit: nine 0s + one 100 → 100 flagged as outlier.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
