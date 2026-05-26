# Architectural 5: Ke gate (error >= 0) undocumented

**File:** `pid_controller/__init__.py:582-585`

**Problem:** Implicit feedforward gate not in docstring or architecture docs.

**Fix:**
1. Subsumed by H14 (remove or smooth gate).
2. If kept: document in PID docstring + CLAUDE.md "Outdoor compensation" subsection.
3. If removed: remove ref to gate in any architecture doc.

**Test:** Doc review.

**Risk:** Low.

**Depends on:** H14.

**Blocks:** none.
