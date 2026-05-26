# Architectural 01: Unify is_paused into PauseDetector

**File:** `state_attributes.py:248-267`, `services/scheduled.py:257-286`, `status_manager.is_paused()`

**Problem:** Same logic (learning_grace + contact_open + humidity should_pause) implemented 3× with subtle diffs.

**Fix:**
1. Create `managers/pause_detector.py` `PauseDetector` class.
2. Inputs: ThermostatState protocol with grace_end, contact_open, humidity_detector.
3. Replace all 3 call sites.
4. Add unit tests.

**Test:** Unit: each subsystem triggers pause; existing integration tests pass.

**Risk:** Med. Behavior divergence between current impls must be reconciled.

**Depends on:** M11 (extraction work).

**Blocks:** none.

**Unresolved:** Reconcile humidity mode-awareness inconsistency: should scheduled.py honor mode-aware behavior of status_manager?
