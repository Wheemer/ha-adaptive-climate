# Low 24: Hardcoded version `5` instead of constant

**File:** `adaptive/persistence.py:39, 211`

**Problem:** `STORAGE_VERSION` defined; use it.

**Fix:**
1. Replace `5` with `STORAGE_VERSION` at both sites.

**Test:** Existing tests pass.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
