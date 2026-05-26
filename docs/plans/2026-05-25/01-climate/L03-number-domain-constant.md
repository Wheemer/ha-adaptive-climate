# Low 03: bare `NUMBER_DOMAIN = "number"` magic string

**File:** `custom_components/adaptive_climate/climate.py:20-22`

**Problem:** Magic string for number domain; could import from HA.

**Fix:**
1. Try import: `from homeassistant.components.number.const import DOMAIN as NUMBER_DOMAIN` with try/except fallback to literal.

**Test:** Import succeeds across supported HA versions.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
