# Low 07: Document `async_cleanup` must be last action

**File:** `central_controller.py:632-656`

**Problem:** Fifth task could be created during cleanup iteration.

**Fix:**
1. Document terminal-call contract in docstring.
2. Optional: set `_closed` flag (covered by H14).

**Test:** N/A.

**Risk:** Low.

**Depends on:** H14.

**Blocks:** none.
