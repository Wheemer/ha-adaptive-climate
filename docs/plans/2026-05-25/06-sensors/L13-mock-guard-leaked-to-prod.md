# Low 13: MagicMock guard in production code

**File:** `managers/state_attributes.py:367-376`

**Problem:** `isinstance(current_temp, (int, float))` excludes Decimal/numpy. Comment admits MagicMock workaround.

**Fix:**
1. Move MagicMock guard into test fixtures (e.g., return real float from mock).
2. Broaden type check to numbers.Real if needed.

**Test:** Existing tests pass; production code clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
