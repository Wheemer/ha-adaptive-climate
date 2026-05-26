# Low 02: `HVACMode = None` default uses TYPE_CHECKING-only symbol

**File:** `adaptive/learning.py:352`

**Problem:** Relies on `from __future__ import annotations`; pyright strict may complain.

**Fix:**
1. Change to `mode: "HVACMode | None" = None` with string forward-ref, OR
2. Move `HVACMode` to runtime import.

**Test:** Pyright strict clean; runtime behavior unchanged.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
