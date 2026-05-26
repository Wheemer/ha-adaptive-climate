# Medium 04: Validation dual-condition misses slow degradation

**File:** `adaptive/validation.py:266`

**Problem:** `recent > baseline * 1.5 AND recent > 0.3`. Baseline=0.4, recent=0.5 (worse) doesn't trigger because 0.5 < 0.6.

**Fix:**
1. Switch to additive: `recent > baseline + max(baseline * 0.5, 0.15)`.
2. Remove absolute 0.3 threshold; absolute floor 0.15 handled by additive.

**Test:** Unit: baseline=0.4, recent=0.5 → triggers; baseline=0.05, recent=0.3 → triggers; baseline=0.05, recent=0.1 → no trigger.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
