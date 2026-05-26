# Medium 10: HA-import fallback silently substitutes string sentinels

**File:** `managers/heater_controller.py:43-63`

**Problem:** Broad try/except on full HA import block. New HA version removing a symbol → fallback strings used silently → wrong service params (e.g., `position=...` to lights).

**Fix:**
1. Narrow try/except to only symbols genuinely optional for tests.
2. Remove fallback for required symbols; rely on test mocks.
3. Update test fixtures to provide proper HA mocks.

**Test:** Run test suite; assert no fallback path hit in normal HA install.

**Risk:** Med — may break test setup if fixtures incomplete.

**Depends on:** none.

**Blocks:** none.
