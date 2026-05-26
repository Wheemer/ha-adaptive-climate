# Medium 12: Float key lookup in _preset_temp_modes

**File:** `managers/temperature_manager.py:243-247`

**Problem:** `if temperature in self._preset_temp_modes` — float key dict lookup is fragile.

**Fix:**
1. Iterate items; use `math.isclose(temperature, key, abs_tol=0.05)`.
2. Return match on first close key.

**Test:** Unit test with stored 19.99999 vs lookup 20.0 — assert match within tolerance.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
