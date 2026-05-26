# Medium 14: `CycleEvent` should be `TypeAlias`

**File:** `managers/events.py:177-181`

**Problem:** Stringified union, no formal `TypeAlias`. Worse IDE/type-checker support.

**Fix:**
1. `from typing import TypeAlias`.
2. Declare `CycleEvent: TypeAlias = Union[...]`.

**Test:** Pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
