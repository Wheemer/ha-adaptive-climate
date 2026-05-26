# Medium 07: `apply_heating_rate_gain` hard wall vs diminishing

**File:** `adaptive/confidence_contribution.py:145-162`

**Problem:** After cap, every rise-time cycle returns 0; no diminishing return signal.

**Fix:**
1. Add `DIMINISHING_RATE_HEATING_RATE` constant (e.g. 0.1).
2. After cap: return `gain * DIMINISHING_RATE_HEATING_RATE` (no tracker increment).
3. Or document hard-wall rationale and keep current behavior.

**Test:** Unit: cap reached → next gain returns small diminishing positive.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Confirm diminishing semantics matches design intent (vs hard wall).
