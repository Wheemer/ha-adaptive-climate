# Low 01: Unused `datetime` import

**File:** `coordinator.py:8`

**Problem:** Only `timedelta` used directly; `datetime` only in type annotations on line 377.

**Fix:**
1. Drop unused import.
2. Use `from datetime import datetime` only if needed for runtime.

**Test:** Ruff clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
