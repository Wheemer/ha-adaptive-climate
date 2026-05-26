# Low 03: _increment_cycle_count confusing is_now_off arg

**File:** `managers/heater_controller.py:485-503`

**Problem:** `is_now_off` arg always True at callers; inverts internally to derive `_last_*_state`.

**Fix:**
1. Drop the arg (always True).
2. OR rename to reflect actual semantic.

**Test:** Existing tests pass.

**Risk:** Low.

**Depends on:** H01.

**Blocks:** none.
