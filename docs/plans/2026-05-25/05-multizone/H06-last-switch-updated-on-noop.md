# High 06: `_last_switch` bumped even when apply fails

**File:** `managers/auto_mode_switching.py:175-268`

**Problem:** `_last_switch` updated on every successful evaluation, but if `_apply_house_mode` fails (no zones, all OFF, service errors), user locked out for `min_switch_interval`.

**Fix:**
1. Don't update `_last_switch` inside `async_evaluate`.
2. Expose `mark_switched()` method.
3. Caller (`coordinator._async_evaluate_auto_mode`) calls `mark_switched()` only after confirming ≥1 zone switched.
4. Align with Architectural A03 split into pure compute + record steps.

**Test:** Unit: simulate apply failure, assert next evaluation not rate-limited. Successful switch → next evaluation rate-limited.

**Risk:** Low.

**Depends on:** none.

**Blocks:** A03.
