# Medium 03: `HVACMode` imported inside `get_active_zone_setpoints`

**File:** `coordinator.py:515-533`

**Problem:** Duplicate import (already at module level line 13).

**Fix:**
1. Drop inline import.
2. Use module-level `HVACMode`.

**Test:** Unit: existing tests still pass.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
