# Low 07: TODO comments in production

**File:** `adaptive/learning.py:1163`

**Problem:** `# TODO: Add effective_duty to metrics`, `# TODO: Add night setback tracking` — rot.

**Fix:**
1. Either implement (track as separate plan if substantive) or convert to GitHub issues.
2. Delete TODO comments.

**Test:** Grep for `TODO` in learning.py → 0 results (or only with linked issue).

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Are these TODOs trackable features or stale?
