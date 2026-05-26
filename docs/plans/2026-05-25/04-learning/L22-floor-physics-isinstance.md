# Low 22: `isinstance(..., (int, float))` legacy style

**File:** `adaptive/floor_physics.py:93`

**Problem:** Tuple form is OK but old. PEP 604 not supported at runtime for `isinstance`.

**Fix:**
1. Leave as-is (PEP 604 isinstance only Python 3.10+ with limits).
2. Or use `numbers.Real`.

**Test:** None.

**Risk:** Low — likely WONTFIX.

**Depends on:** none.

**Blocks:** none.
