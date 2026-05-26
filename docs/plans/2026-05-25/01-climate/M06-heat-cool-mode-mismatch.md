# Medium 06: HEAT_COOL accepted by setter but absent from `_attr_hvac_modes`

**File:** `custom_components/adaptive_climate/climate.py:1077,1087,1130`

**Problem:** Setter allows HEAT_COOL; not declared in supported modes. UI/services treat as unsupported.

**Fix:**
1. Explicit reject HEAT_COOL with `ValueError("HEAT_COOL not supported")`.
2. Or add HEAT_COOL to `_attr_hvac_modes` and wire actual logic.

**Test:** Unit: setting HEAT_COOL raises clear error.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
