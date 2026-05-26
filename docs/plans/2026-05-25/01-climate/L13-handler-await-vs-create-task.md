# Low 13: handler awaits control loop directly; consider `async_create_task`

**File:** `custom_components/adaptive_climate/climate_handlers.py:147,177,230`

**Problem:** Handlers `await self._async_control_heating(...)`; in hot paths may block.

**Fix:**
1. Profile handler latency.
2. If hot: replace with `hass.async_create_task(self._async_control_heating(...))`.
3. Document trade-off (lose error propagation).

**Test:** Manual: rapid sensor updates do not stall HA.

**Risk:** Med — fire-and-forget loses error visibility.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Is fire-and-forget acceptable given existing single-flight in control loop?
