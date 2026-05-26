# Medium 12: actuator_wear cycles attr None → TypeError

**File:** `sensors/actuator_wear.py:140`

**Problem:** `attributes.get(attr_name, 0)`; if attr is explicitly None, arithmetic raises.

**Fix:**
1. `int(climate_state.attributes.get(attr_name) or 0)`.

**Test:** Unit: attr=None; assert no exception.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
