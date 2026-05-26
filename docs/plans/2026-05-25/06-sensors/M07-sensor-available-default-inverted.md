# Medium 07: sensor_available defaults True when no sensor

**File:** `sensors/health.py:139-143`

**Problem:** When `climate_entity_id` is None, defaults `sensor_available=True`. Inverted.

**Fix:**
1. Default `sensor_available=False`.
2. Set True only when verified available.

**Test:** Unit: climate_entity_id=None; assert False.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
