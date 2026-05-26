# Medium 11: is_paused logic duplicated 3 places

**File:** `services/scheduled.py:255-294` (and `state_attributes.py:248-267`, `status_manager.is_paused()`)

**Problem:** Pause detection (learning_grace + contact_open + humidity should_pause) duplicated with subtle differences.

**Fix:**
1. Extract `PauseDetector` class or `get_is_paused(thermostat)` helper.
2. Replace all 3 call sites.
3. Add unit tests.

**Test:** Unit: each pause condition triggers detector; integration: existing tests pass.

**Risk:** Med.

**Depends on:** none.

**Blocks:** A01 (PauseDetector architecture).
