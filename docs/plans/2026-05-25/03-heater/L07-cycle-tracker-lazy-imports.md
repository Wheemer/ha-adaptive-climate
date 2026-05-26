# Low 07: Six lazy local imports in cycle_tracker

**File:** `managers/cycle_tracker.py:96-102, 449, 472, 505, 577, 735`

**Problem:** Local imports inside methods to break circulars; six sites excessive.

**Fix:**
1. Consolidate at module top with `TYPE_CHECKING` guards.
2. Refactor circular dependency if needed (extract shared types to a `types.py`).

**Test:** No regressions; imports work.

**Risk:** Low-Med — circular imports may resurface.

**Depends on:** none.

**Blocks:** none.
