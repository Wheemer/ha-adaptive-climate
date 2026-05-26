# Low 04: Aggregate demand dict uses string keys

**File:** `coordinator.py:447-450`

**Problem:** Keys "heating"/"cooling" as strings; consider enum matching `HVACMode`.

**Fix:**
1. Use `HVACMode.HEAT`/`HVACMode.COOL` as dict keys.
2. Update consumers.

**Test:** Existing tests pass after key update.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
