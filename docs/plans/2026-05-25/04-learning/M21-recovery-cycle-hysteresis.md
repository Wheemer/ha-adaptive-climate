# Medium 21: Recovery classification uses pre-update confidence → flicker

**File:** `adaptive/learning.py:1182-1187, 1166-1168`

**Problem:** Cycle classification uses pre-update confidence; borderline cycles flicker recovery/maintenance.

**Fix:**
1. Add hysteresis: `is_stable_promote = confidence > tier1 * 0.85`; `is_stable_demote = confidence < tier1 * 0.75`.
2. Track `_is_stable_latched` flag transitioned only when crossing band.

**Test:** Unit: confidence oscillating around tier1 → classification stable (no flicker).

**Risk:** Low.

**Depends on:** H11 (uses real scaled tier1).

**Blocks:** none.
