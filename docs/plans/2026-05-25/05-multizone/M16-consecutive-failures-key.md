# Medium 16: `_consecutive_failures` keyed by entity_id only

**File:** `central_controller.py:78`

**Problem:** Turn-on failure + turn-off success on same entity resets counter despite turn-on still failing. Probably acceptable.

**Fix:**
1. Key by `(entity_id, service)` tuple.
2. Or document accepted limitation.

**Test:** Unit: alternating on-fail/off-pass, assert turn-on counter not reset.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
