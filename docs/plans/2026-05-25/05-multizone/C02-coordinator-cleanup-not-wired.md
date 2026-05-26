# Critical 02: coordinator `async_cleanup` never invoked on unload

**File:** `coordinator.py:62-80, 668-696`

**Problem:** `_setup_outdoor_temp_listener()` + `_startup_eval_unsub` timer scheduled in `__init__`. `async_cleanup()` is the only unsubscriber but nothing calls it from `async_unload_entry`. Every config reload leaks listeners + EMA tasks + auto-mode tasks for HA process lifetime.

**Fix:**
1. In `__init__.py` `async_unload_entry`, call `await coordinator.async_cleanup()`.
2. Same path: `await coordinator.central_controller.async_cleanup()`.
3. Verify all subscriptions tracked (outdoor temp listener, startup eval timer, auto-mode tasks).
4. Add idempotency check so double-cleanup is safe.

**Test:** Integration: reload config entry 5x, assert `hass.bus._listeners` count stable. Unit: assert `async_cleanup` unsubscribes outdoor listener and cancels startup timer.

**Risk:** Med — touches lifecycle; missing a subscription leaves leak.

**Depends on:** none.

**Blocks:** H10 (zone unregister cleanup).
