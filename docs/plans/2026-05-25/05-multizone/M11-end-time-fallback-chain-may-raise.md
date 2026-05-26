# Medium 11: End-time fallback chain raises if `recovery_deadline` malformed

**File:** `managers/night_setback_calculator.py:282-302`

**Problem:** If `recovery_deadline` malformed, `int(...)` calls raise.

**Fix:**
1. Wrap `int()` parsing in try/except.
2. Fallback to `07:00` with `_LOGGER.error`.
3. Combine with H13 validation at setup.

**Test:** Unit: malformed deadline, assert fallback to 07:00.

**Risk:** Low.

**Depends on:** H13.

**Blocks:** none.
