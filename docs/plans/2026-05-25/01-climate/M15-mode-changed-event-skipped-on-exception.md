# Medium 15: ModeChangedEvent skipped if `_async_heater_turn_off` raises

**File:** `custom_components/adaptive_climate/climate.py:1185-1191,1121`

**Problem:** Event emitted only after turn-off succeeds. If turn-off swallows exception, subscribers miss off-transition.

**Fix:**
1. Emit ModeChangedEvent in try/finally to guarantee fire.
2. Or emit BEFORE turn-off (subscribers prepare for OFF), with separate ERROR event on failure.

**Test:** Unit: force turn_off to raise → event still emitted.

**Risk:** Low.

**Depends on:** C01.

**Blocks:** none.
