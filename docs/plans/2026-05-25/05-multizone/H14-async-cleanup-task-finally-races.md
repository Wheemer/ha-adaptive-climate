# High 14: `async_cleanup` leaves task `finally` blocks racing torn-down state

**File:** `central_controller.py:632-656`

**Problem:** After cancel + await, delayed task `finally` (lines 204-207) tries `async with self._startup_lock:` on possibly torn-down controller.

**Fix:**
1. Add `_closed: bool = False` flag.
2. Set `_closed = True` first in `async_cleanup`.
3. Delayed task body checks `if self._closed: return` before re-acquiring lock.
4. Document that `async_cleanup` is terminal.

**Test:** Unit: cancel startup, immediately call cleanup, assert no errors from finally block.

**Risk:** Med — interacts with C07 refactor.

**Depends on:** C07.

**Blocks:** none.
