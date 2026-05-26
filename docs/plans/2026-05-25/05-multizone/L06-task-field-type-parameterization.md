# Low 06: Task fields lack `asyncio.Task[None]` parameterization

**File:** `central_controller.py:65-72`

**Problem:** Minor type hint quality.

**Fix:**
1. Add `asyncio.Task[None] | None` annotation.

**Test:** Pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
