# High 09: `register_zone` resets demand state on re-registration

**File:** `coordinator.py:294-309`

**Problem:** Duplicate registration overwrites zone_data and resets `_demand_states[zone_id]` to `{"demand": False, "mode": None}`. During config reload, actively-heating zone's demand wiped → central controller shuts off boiler mid-cycle.

**Fix:**
1. Only initialize `_demand_states[zone_id]` if `zone_id not in self._demand_states`.
2. Log debug when preserved across re-registration.
3. Add test for reload-during-heating scenario.

**Test:** Unit: register zone, set demand True, re-register, assert demand preserved.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
