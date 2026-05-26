# Critical 08: `apply_adjustment` can corrupt cumulative tracker to negative

**File:** `adaptive/undershoot_detector.py:357-396`

**Problem:** `cumulative_ki_multiplier *= multiplier` updates before sanity check. If `get_adjustment` ever returns ≤0 (bad restore makes `max_allowed` negative), cumulative goes negative → next call `min(positive, negative) = negative` → gate broken permanently.

**Fix:**
1. Clamp incoming: `multiplier = max(1.0, get_adjustment(...))`.
2. Clamp result: `cumulative_ki_multiplier = min(MAX_UNDERSHOOT_KI_MULTIPLIER, max(1.0, cumulative * multiplier))`.
3. On restore, also clamp loaded `cumulative_ki_multiplier` to `[1.0, MAX_UNDERSHOOT_KI_MULTIPLIER]`.

**Test:** Unit: inject restored `cumulative = -0.5` → first call self-heals to 1.0; inject `cumulative > cap` → clamped at cap.

**Risk:** Low — defensive.

**Depends on:** C07.

**Blocks:** none.
