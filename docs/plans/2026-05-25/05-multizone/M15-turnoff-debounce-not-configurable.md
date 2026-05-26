# Medium 15: `TURN_OFF_DEBOUNCE_SECONDS` not configurable

**File:** `central_controller.py:24-25, 269-311`

**Problem:** Hard-coded 10s. Hides flickering risk for large flywheels (district heating).

**Fix:**
1. Expose as domain config under `central_controller:`.
2. Or scale per heating type (e.g. 30s floor, 5s forced_air).
3. Default 10s preserved.

**Test:** Unit: override config, assert debounce uses new value.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Config option vs heating-type scaling?
