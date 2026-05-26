# High 11: broken type annotation `set_hvac_mode(hvac_mode: (HVACMode, str))`

**File:** `custom_components/adaptive_climate/climate.py:1077`

**Problem:** Tuple where union meant; pyright reads as `tuple[type[HVACMode], type[str]]`.

**Fix:**
1. Change to `hvac_mode: HVACMode | str`.
2. Same audit on async variant signature.

**Test:** Pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** M03.
