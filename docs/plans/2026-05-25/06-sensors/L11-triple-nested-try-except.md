# Low 11: Triple-nested try/except for AttributeError/TypeError

**File:** `services/scheduled.py:260-286`

**Problem:** Code smell.

**Fix:**
1. Use `with contextlib.suppress(AttributeError, TypeError):` per block.

**Test:** Existing tests pass.

**Risk:** Low.

**Depends on:** M11 (related cleanup).

**Blocks:** none.
