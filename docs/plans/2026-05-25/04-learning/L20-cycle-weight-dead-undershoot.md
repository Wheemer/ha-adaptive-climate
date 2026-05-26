# Low 20: Undershoot outcome_factor unreachable in good-cycle path

**File:** `adaptive/cycle_weight.py:113`

**Problem:** `is_good_cycle` filters undershoot ≥ threshold; UNDERSHOOT outcome_factor 0.5 never hit in reward path.

**Fix:**
1. Add comment explaining unreachability (for penalty path use).
2. Or restructure: only compute outcome_factor at use sites that need it.
3. Confirm with H10 fix (weighted penalties) — may become reachable.

**Test:** Coverage report shows branch reachable post-H10.

**Risk:** Low.

**Depends on:** H10.

**Blocks:** none.
