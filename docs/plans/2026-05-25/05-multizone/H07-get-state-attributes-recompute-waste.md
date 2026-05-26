# High 07: `get_state_attributes` recomputes ISO strings every read

**File:** `managers/auto_mode_switching.py:286-304`

**Problem:** ISO computed on every attribute read. Wasted work.

**Fix:**
1. Cache `_cached_next_allowed_switch_iso` + `_cached_last_switch_iso`.
2. Recompute only when `_last_switch` changes (in `mark_switched` from H06).
3. Return cached strings.

**Test:** Unit: call `get_state_attributes` 100x, assert ISO computed once.

**Risk:** Low.

**Depends on:** H06.

**Blocks:** none.
