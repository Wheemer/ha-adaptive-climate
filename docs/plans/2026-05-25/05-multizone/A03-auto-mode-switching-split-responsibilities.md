# Arch 03: Split `AutoModeSwitchingManager.async_evaluate`

**File:** `managers/auto_mode_switching.py:175-268`

**Problem:** Mixes rate-limit, season classification, mode decision, bookkeeping.

**Fix:**
1. `_compute_target_mode()` — pure function (median + season + threshold).
2. `_should_switch()` — rate-limit check.
3. `_record_switch()` — bookkeeping.
4. `async_evaluate` orchestrates the three.
5. Resolves H06 naturally.

**Test:** Unit fixtures against each function in isolation.

**Risk:** Low.

**Depends on:** H06.

**Blocks:** none.
