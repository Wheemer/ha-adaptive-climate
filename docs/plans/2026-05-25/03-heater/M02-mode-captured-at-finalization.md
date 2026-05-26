# Medium 02: Mode re-read at finalization, not cycle start

**File:** `managers/cycle_metrics.py:480-490`

**Problem:** `_get_hvac_mode()` called at finalization. User mode flip after SETTLING_STARTED → wrong mode in metrics row.

**Fix:**
1. Capture `_cycle_mode` at `_on_cycle_started`.
2. Thread through `record_cycle_metrics`.
3. Remove re-read at finalization.

**Test:** Unit test cycle start in HEAT, user flips to OFF post-SETTLING_STARTED → metrics row mode=HEAT.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
