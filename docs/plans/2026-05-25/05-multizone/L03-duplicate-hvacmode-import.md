# Low 03: Duplicate `HVACMode` import

**File:** `coordinator.py:521`

**Problem:** Already imported at module level line 13.

**Fix:**
1. Drop inline import.

**Test:** Ruff clean.

**Risk:** Low.

**Depends on:** M03.

**Blocks:** none.
