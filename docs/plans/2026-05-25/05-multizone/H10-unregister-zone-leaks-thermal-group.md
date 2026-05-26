# High 10: `unregister_zone` doesn't notify thermal_group_manager

**File:** `coordinator.py:340-344`

**Problem:** Zone removed from `_demand_states` but not from `thermal_group_manager` or `central_controller`. Stale references leak.

**Fix:**
1. Call `self._thermal_group_manager.remove_zone(zone_id)` if manager exists.
2. Call `self._central_controller.remove_zone(zone_id)` if applicable.
3. Add `remove_zone` method to managers if missing.
4. Document zone-lifecycle contract (consider pub/sub from A02).

**Test:** Unit: register zone in thermal group, unregister, assert removed. Integration: reload entry, assert no stale zone refs.

**Risk:** Low.

**Depends on:** C02.

**Blocks:** none.
