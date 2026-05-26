# Low 01: typing.Callable instead of collections.abc.Callable

**File:** `managers/heater_controller.py:7`

**Problem:** Python 3.9+ prefers `collections.abc.Callable`.

**Fix:**
1. Replace `from typing import ... Callable` with `from collections.abc import Callable`.

**Test:** Existing tests pass; pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
