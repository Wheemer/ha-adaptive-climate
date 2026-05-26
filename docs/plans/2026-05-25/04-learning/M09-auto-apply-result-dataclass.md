# Medium 09: `AutoApplyGateResult` dataclass instead of 4-tuple

**File:** `adaptive/auto_apply.py:140`

**Problem:** `tuple[bool, int|None, int|None, int|None]` unwieldy; `None` semantics implicit.

**Fix:**
1. Add `@dataclass(frozen=True) class AutoApplyGateResult: passed: bool; min_interval_hours: int|None; min_adjustment_cycles: int|None; min_cycles: int|None`.
2. Update return + caller unpacking.
3. Add `is_blocked` property for readability.

**Test:** Existing tests pass after caller refactor.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
