# High 09: delta_t=0 silently dropped as None

**File:** `sensors/energy.py:233`

**Problem:** `supply - return if supply > return else None` drops legitimate 0 (idle). Downstream attrs inconsistent.

**Fix:**
1. Replace with `self._delta_t = max(0.0, supply_temp - return_temp)`.
2. Update attr reporting accordingly.

**Test:** Unit: supply==return; assert `delta_t == 0.0`, `heat_output == 0`.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
