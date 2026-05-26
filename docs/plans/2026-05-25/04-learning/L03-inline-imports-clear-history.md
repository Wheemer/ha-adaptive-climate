# Low 03: Inline imports in `clear_history`

**File:** `adaptive/learning.py:898-923`

**Problem:** Inline `from ..const import HeatingType`, etc. — already at module top.

**Fix:**
1. Remove inline imports.
2. Use top-level symbols.

**Test:** Lint / import order check.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
