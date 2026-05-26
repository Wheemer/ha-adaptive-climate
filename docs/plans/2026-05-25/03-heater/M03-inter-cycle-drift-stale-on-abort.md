# Medium 03: inter_cycle_drift compares against cycle-before-last on abort

**File:** `managers/cycle_metrics.py:467-468`

**Problem:** `_prev_cycle_end_temp` only updated when previous cycle finalized. Aborted cycles (contact_sensor, setpoint_major) skip `record_cycle_metrics` → next cycle drift compares against stale temp.

**Fix:**
1. Reset `_prev_cycle_end_temp = None` on abort paths.
2. OR store with timestamp; discard if stale (>2h or >1 cycle gap).
3. Skip drift calc when prev is None/stale; record as `None` in metrics row.

**Test:** Unit test recovery → abort → new cycle: assert `inter_cycle_drift is None` (or correct value), not stale comparison.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
