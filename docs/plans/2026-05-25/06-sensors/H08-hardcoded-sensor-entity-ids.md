# High 08: Hardcoded sensor entity_ids assume no rename

**File:** `sensors/comfort.py:250,288`, `sensors/energy.py:94,342`, `sensors/health.py:111,121`, `services/scheduled.py:46,56,212,222`

**Problem:** `f"sensor.{zone_id}_{name}"` breaks if user renames entity (entity_id drifts, unique_id is fixed).

**Fix:**
1. Use `entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)` to resolve at runtime.
2. Better: expose direct method on sensor instance via coordinator/shared registry.
3. Update all listed call sites.

**Test:** Integration: rename a sensor in registry; assert cross-sensor lookups still work.

**Risk:** Med. Many call sites.

**Depends on:** none.

**Blocks:** A03 (sensor coupling refactor).
