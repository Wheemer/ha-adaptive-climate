# Low 02: try/except ImportError fallback invisible to type checker

**File:** `coordinator.py:16-23`

**Problem:** Normal HA pattern but invisible to pyright strict.

**Fix:**
1. Add module-level comment explaining test/HA dual-import.
2. Document in CLAUDE.md style guide if not already.

**Test:** N/A.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
