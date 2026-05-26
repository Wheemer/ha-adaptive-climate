# Low 10: async_create_task without reference (lifecycle)

**File:** `managers/cycle_metrics.py:550-551`

**Problem:** `hass.async_create_task(self._on_auto_apply_check())` — task may be lost during shutdown.

**Fix:**
1. Replace with `hass.async_create_background_task(coro, "adaptive_climate_auto_apply")` (HA 2024+).

**Test:** No regressions; HA shutdown cleanly awaits background task.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
