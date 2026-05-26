# Architectural 2: Two parallel APIs for KeManager (Protocol + callback)

**File:** `managers/ke_manager.py:43-122,151-197`

**Problem:** Dual paths violate CLAUDE.md; doubles surface, harder type-check.

**Fix:**
1. See M23. Delete callback path entirely.
2. Add Protocol-only constructor signature.
3. Update tests.

**Test:** Coverage drops to zero on deleted branches.

**Risk:** Med.

**Depends on:** M23.

**Blocks:** none.
