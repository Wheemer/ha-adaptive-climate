# Architectural 01: AdaptiveThermostat is a god object

**File:** `custom_components/adaptive_climate/climate.py` (~1940 lines)

**Problem:** Entity mixes platform plumbing, restoration, manager wiring, services, event subscribers, 20+ setter callbacks. Mixin split doesn't solve cohesion — mixins still reach into host privates.

**Fix:**
1. Each manager owns its state, exposes typed interface.
2. Entity dispatches only.
3. Extract: cycle handlers, PID-history services, state setters → dedicated modules.
4. See M01 for concrete extraction targets.

**Test:** Module under 800 lines; pyright clean; integration test parity.

**Risk:** High — multi-PR effort, regression surface.

**Depends on:** M01, H02, A02, A03.

**Blocks:** none.

**Unresolved:** Should this be staged across multiple releases or as one big PR?
