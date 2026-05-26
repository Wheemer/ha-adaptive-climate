# Architectural 04: multiple stores of truth for HVAC mode string

**File:** `climate.py` (~15 inline `self._hvac_mode.value` computations), `climate_control.py:59`, `climate.py:1173`

**Problem:** Enum + inline `.value` + inconsistent default ("off" vs None) sprinkled. Inconsistent defaults are a bug surface.

**Fix:**
1. Add cached property `hvac_mode_str -> str` returning `.value` with fixed default "off".
2. Replace all inline `.value` accesses.
3. Standardize default everywhere.

**Test:** Grep zero `_hvac_mode.value` outside the property; tests unaffected.

**Risk:** Low-Med.

**Depends on:** none.

**Blocks:** none.
