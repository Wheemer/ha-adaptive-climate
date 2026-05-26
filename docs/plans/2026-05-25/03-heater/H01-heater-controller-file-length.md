# High 01: heater_controller.py exceeds 800-line limit (1132 lines)

**File:** `managers/heater_controller.py`

**Problem:** Violates CLAUDE.md max file length.

**Fix:**
1. Extract timer/debounce logic (`_emit_settling_started_*`, `_emit_heating_started_delayed`, `cancel_pending_timers`) → `heater_timers.py`.
2. Extract service-call wrapper (`_async_call_heater_service`, `_get_number_entity_domain`) → `heater_service_caller.py`.
3. Extract cycle-counting/cycle-active bookkeeping (`_increment_cycle_count`, `_last_*_state`) → `heater_cycle_bookkeeper.py`.
4. Keep public `HeaterController` API stable; compose extracted helpers.

**Test:** Existing heater/cycle test suites pass unchanged.

**Risk:** Med — large refactor; risk of subtle state-ownership shifts.

**Depends on:** C01, C02, C03 (do extractions after critical fixes land to avoid merge thrash).

**Blocks:** H02, H03, H04, H06 (all touch this file).
