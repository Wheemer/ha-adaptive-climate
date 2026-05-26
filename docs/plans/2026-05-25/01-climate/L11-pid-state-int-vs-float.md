# Low 11: `_p = _i = _d = _e = _dt = 0` mixes int and float

**File:** `custom_components/adaptive_climate/climate.py:407`

**Problem:** Should be 0.0 for float-typed fields.

**Fix:** Change to `= 0.0`.

**Test:** Pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
