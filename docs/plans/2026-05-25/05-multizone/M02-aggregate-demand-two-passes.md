# Medium 02: `get_aggregate_demand` two passes over `_demand_states`

**File:** `coordinator.py:434-450`

**Problem:** Two passes (heat + cool) over same dict on every state attribute read.

**Fix:**
1. Single pass returning `{"heating": bool, "cooling": bool}`.
2. Or cache result invalidated on demand-state change.

**Test:** Unit: assert single pass produces correct result.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
