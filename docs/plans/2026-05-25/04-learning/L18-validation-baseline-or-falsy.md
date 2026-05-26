# Low 18: `baseline or 0.1` swallows real 0.0

**File:** `adaptive/validation.py:107`

**Problem:** Falsy 0.0 → 0.1; clean baseline silently lost.

**Fix:**
1. `baseline = self._validation_baseline_overshoot if self._validation_baseline_overshoot is not None else 0.1`.

**Test:** Unit: baseline=0.0 → preserved as 0.0 (paired with H12 absolute-floor handling).

**Risk:** Low.

**Depends on:** H12 (handles 0 case downstream).

**Blocks:** none.
