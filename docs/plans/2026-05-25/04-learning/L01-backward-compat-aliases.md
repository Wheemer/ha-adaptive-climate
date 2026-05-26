# Low 01: Backward-compat property aliases pollute production

**File:** `adaptive/learning.py:224-350`

**Problem:** ~125 lines of test-only aliases mix-set across heat/cool; easy misuse.

**Fix:**
1. Audit which tests actually use each alias.
2. Migrate tests to use public API (`get_cycle_count(mode)`, `get_confidence(mode)`).
3. Delete aliases or move to `tests/conftest.py` helper.

**Test:** Existing test suite passes; no production code references aliases.

**Risk:** Med — broad test refactor.

**Depends on:** none.

**Blocks:** C01.
