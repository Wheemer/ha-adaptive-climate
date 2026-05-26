# Medium 18: demand-switch cycle_count lossy on toggle

**File:** `state_attributes.py:41-42` + `state_restorer.py:178-184`

**Problem:** demand_switch=True stores bare int; restorer treats as `{heater: N, cooler: 0}`. Lossy if user toggles demand_switch off.

**Fix:**
1. Always store as dict `{heater, cooler}` even for demand_switch.
2. Or persist demand_switch flag and adjust restore.

**Test:** Unit: toggle demand_switch off; assert cooler count preserved.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
