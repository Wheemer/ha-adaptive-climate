# Architectural 03: Cross-module private access (multiple)

**File:** `managers/pwm_controller.py:341`; `managers/cycle_tracker.py:237-272`

**Problem:** `_has_demand` write from another module; `_interruption_history`, `_was_clamped`, `_device_on_time`, `_integral_at_*`, `_transport_delay_minutes` exposed solely for tests.

**Fix:**
1. Public read-only `CycleMetricsView` for test inspection.
2. Private mutation API guarded inside manager.
3. Replace external private attr access (covered partly by H06).

**Test:** Refactor doesn't break test suite.

**Risk:** Med — touches test code extensively.

**Depends on:** H06.

**Blocks:** none.
