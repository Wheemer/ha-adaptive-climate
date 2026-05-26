# Medium 16: should_pause bool() wrap conflates types

**File:** `managers/status_manager.py:178`

**Problem:** `bool(...)` wraps truthy-check; functionally OK but should_pause could return non-bool.

**Fix:**
1. Annotate `should_pause -> bool` return type.
2. Drop `bool()` wrap.

**Test:** Pyright strict.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
