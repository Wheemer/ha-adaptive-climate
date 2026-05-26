# Low 05: `get_previous_pid` always returns None

**File:** `adaptive/learning.py:925-935`

**Problem:** Deprecated zombie method.

**Fix:**
1. Delete method.
2. Audit callers; remove or migrate.
3. Or mark with `@deprecated` and removal date.

**Test:** Grep for callers → none remain.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
