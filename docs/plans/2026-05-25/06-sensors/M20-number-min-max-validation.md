# Medium 20: number.py min/max hardcoded; verify default fits

**File:** `number.py:48-49`

**Problem:** `min=1, max=30` hardcoded. Verify `DEFAULT_LEARNING_WINDOW_DAYS` within range.

**Fix:**
1. Assert/validate default at import.
2. Add comment linking to const.

**Test:** Unit: instantiate; assert no ValueError.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
