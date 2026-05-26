# Medium 08: Comfort score is float "87.0", no PERCENTAGE unit

**File:** `sensors/comfort.py:217`

**Problem:** `round(x, 0)` returns float. State_class=MEASUREMENT displays "87.0". No native_unit_of_measurement set.

**Fix:**
1. `self._state = int(round(comfort_score))`.
2. Set `_attr_native_unit_of_measurement = PERCENTAGE`.

**Test:** Unit: assert state is int, UoM=%.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
