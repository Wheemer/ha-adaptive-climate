# Low 21: Unknown heating_type silently falls back to convector

**File:** `adaptive/auto_apply.py:33-49`

**Problem:** Typo heating_type returns convector thresholds (shorter cooldowns) for floor.

**Fix:**
1. Raise `ValueError` on unknown heating_type, OR
2. Log WARN with the unknown value + use safest defaults (floor_hydronic).

**Test:** Unit: unknown type → WARN logged + uses floor defaults.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
