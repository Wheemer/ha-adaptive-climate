# Medium 21: Dedup uses 2-decimal round; loses Ki precision

**File:** `managers/pid_gains_manager.py:102-111`

**Problem:** `round(ki, 2)` treats 0.005 and 0.0049 as identical; snapshot skipped though PID got real new Ki.

**Fix:**
1. Use mode-aware rounding: `kp` 2 decimals, `ki` 5 decimals, `kd` 2 decimals, `ke` 4 decimals.
2. Extract to `_round_for_dedup(name, value)` helper.
3. Update both `_gains_match_last_entry` and history snapshot formatting.

**Test:** Unit: change Ki by 0.0001, assert new history entry recorded.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
