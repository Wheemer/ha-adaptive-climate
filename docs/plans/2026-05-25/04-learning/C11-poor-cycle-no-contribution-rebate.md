# Critical 11: Poor cycle penalty doesn't rebate contribution cap

**File:** `adaptive/learning.py:1208` + `adaptive/confidence_contribution.py`

**Problem:** Poor cycle subtracts `0.05` from `current_confidence` but doesn't decrement `_heating_maintenance_contribution`. Cap stays maxed → future maintenance cycles always diminished → system can't re-converge.

**Fix:**
1. On confidence decrease, decrement matching contribution tracker proportionally (`tracker.rebate(mode, delta)`).
2. Add `rebate(mode, amount)` method to `ConfidenceContributionTracker` that floors at 0.
3. Call it from poor cycle path in `learning.py:1208` and any other confidence-decreasing path (search `current_confidence -=`).

**Test:** Unit: simulate fill-to-cap → poor cycle → maintenance cycle now contributes full gain again.

**Risk:** Med — affects long-term convergence behavior.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Rebate proportional to confidence delta or 1:1? Confirm with hvac-expert.
