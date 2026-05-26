# Low 12: `_LOGGER.info` per coordinator tick noisy

**File:** `managers/night_setback_calculator.py:330`

**Problem:** Logs per cycle on every tick.

**Fix:**
1. Demote to `debug` when state unchanged.
2. Log info only on transition.

**Test:** Manual: tail logs, assert no spam.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
