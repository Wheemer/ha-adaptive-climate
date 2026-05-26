# Medium 27: `_dt_discrepancy_last_warned` is module-global mutable dict

**File:** `managers/control_output.py:26`

**Problem:** Per-entity warning state never cleaned on entity removal. Memory leak per reload.

**Fix:**
1. Move to instance attribute `self._dt_discrepancy_last_warned: float = 0.0` in `ControlOutputManager.__init__`.
2. Update warning site to use `self._...`.
3. Remove module-level dict.

**Test:** Unit: reload entity 100 times, assert no module-global growth.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
