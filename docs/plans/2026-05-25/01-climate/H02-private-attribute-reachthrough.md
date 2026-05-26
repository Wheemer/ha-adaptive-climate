# High 02: pervasive private-attribute reach-through across modules

**File:** `climate.py:530,534,1434-1438`, `climate_control.py:78-80,192,216,219,230`

**Problem:** Direct access to `adaptive_learner._auto_apply_count`, `_heating_rate_learner._active_session`, `undershoot_detector._consecutive_failures`. Violates CLAUDE.md ThermostatState Protocol mandate.

**Fix:**
1. Inventory every cross-module `_*` access in climate.py + climate_control.py.
2. Add public accessors on AdaptiveLearner, HeatingRateLearner, UndershootDetector (`auto_apply_count`, `active_heating_session`, `consecutive_failures` properties).
3. Or move session-lifecycle logic into AdaptiveLearner with single facade method.
4. Replace call sites; remove `_*` accesses.

**Test:** Pyright check; unit: AdaptiveLearner facade method invoked by climate_control returns expected state.

**Risk:** Med — touches multiple modules, may surface latent coupling.

**Depends on:** none.

**Blocks:** A02, A03.
