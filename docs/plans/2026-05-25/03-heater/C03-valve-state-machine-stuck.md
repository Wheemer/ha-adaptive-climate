# Critical 03: Valve mode SETTLING_STARTED gated by temp tolerance — cycle hangs

**File:** `managers/heater_controller.py:843-949` (`async_set_valve_value`)

**Problem:** SETTLING_STARTED only emitted when `value < 5.0 AND abs(current-target) <= 0.5`. Valve closing far from target (window opened, mode change) leaves `_cycle_active=True` forever; reopening hits `if new_active and not self._cycle_active` guard so no new CYCLE_STARTED; CycleTrackerManager stuck in HEATING.

**Fix:**
1. Mirror PWM path (`async_set_control_value` line 992): emit SETTLING_STARTED on demand-zero debounce regardless of temp tolerance.
2. Drop temp-tolerance gate from valve branch; keep value<5.0 + demand-zero trigger.
3. Ensure `cancel_pending_timers()` triggers consistent state reset on mode change.

**Test:** Unit/integration: valve open at 50% with temp far from target → force value=0 → assert SETTLING_STARTED fires within debounce, `_cycle_active=False` after.

**Risk:** Med — touches dual-mode state machine; risk of double-emit if not deduped against existing PWM path.

**Depends on:** none.

**Blocks:** H04 (stale hvac_mode in lambdas, same callbacks).
