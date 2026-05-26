# Low 10: `update_days_at_maintenance_cap` invocation cadence unclear

**File:** `managers/night_setback_manager.py:163-177`

**Problem:** Increments by 1 per call. With 30s coordinator loop, 7 days reached in ~3.5 min.

**Fix:**
1. Confirm caller invokes exactly once per day.
2. Add docstring stating contract.
3. Optional: guard via timestamp diff inside method.

**Test:** Unit: simulate multiple calls within same day, assert no double-increment.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
