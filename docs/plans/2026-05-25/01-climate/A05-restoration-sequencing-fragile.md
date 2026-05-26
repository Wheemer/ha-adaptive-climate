# Architectural 05: restoration sequencing is fragile

**File:** `custom_components/adaptive_climate/climate.py` (`async_added_to_hass`)

**Problem:** Listeners attached before restore completes. Failure leaves entity half-init while receiving events.

**Fix:**
1. Reorder `async_added_to_hass`: managers → wiring → restore → cycle_tracker → coordinator → physics → kickoff control loop → ATTACH LISTENERS LAST.
2. Add explicit init phase enum (`UNINIT/RESTORING/READY`) gating event handlers.
3. Handlers no-op when not READY.

**Test:** Unit: force restore failure → no event handler executes mutation.

**Risk:** Med.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Init-phase enum or simpler "ready" boolean?
