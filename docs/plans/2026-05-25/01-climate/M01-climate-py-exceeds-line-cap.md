# Medium 01: climate.py exceeds 800-line cap (1938 lines, 2.4×)

**File:** `custom_components/adaptive_climate/climate.py`

**Problem:** Mixin split moved code without solving cohesion. Bulk remains in climate.py.

**Fix:**
1. Extract preheat/heating-rate cycle handlers (lines 1358-1483) → `adaptive/cycle_handlers.py`.
2. Extract PID-history service methods (1262-1292) → `services/pid_history_service.py`.
3. Extract heater-control facade setters (1663-1738) → `managers/state_callbacks.py`.
4. Confirm each module under 800 lines after split.

**Test:** Pyright clean; pytest passes; no behavior change in integration tests.

**Risk:** Med — large refactor, possible import cycles.

**Depends on:** H02 (private accessors first to make extraction clean).

**Blocks:** A01.
