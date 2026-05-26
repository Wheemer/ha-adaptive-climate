# Low 26: Three nearly-identical try/except blocks

**File:** `managers/learning_gate.py:155-159, 162-166, 169-175`

**Problem:** Boilerplate DRY violation.

**Fix:**
1. Extract `_safe_check(callable, default=False, name="") -> bool` helper.
2. Replace three blocks.

**Test:** Existing tests pass; coverage stable.

**Risk:** Low.

**Depends on:** M22 (narrow excepts first).

**Blocks:** none.
