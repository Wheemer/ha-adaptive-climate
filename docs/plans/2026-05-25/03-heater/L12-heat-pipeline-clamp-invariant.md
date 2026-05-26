# Low 12: HeatPipeline clamps in-flight estimate to transport_delay

**File:** `managers/heat_pipeline.py:51`

**Problem:** `min(time_open, self.transport_delay)` under-reports if `valve_time > transport_delay`.

**Fix:**
1. If C01 = DELETE → moot.
2. If C01 = WIRE → document invariant `valve_time <= transport_delay` OR compute properly accounting for both.

**Test:** Unit test edge case `valve_time > transport_delay`.

**Risk:** Low.

**Depends on:** C01.

**Blocks:** none.
