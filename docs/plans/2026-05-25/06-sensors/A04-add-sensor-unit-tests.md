# Architectural 04: Add sensor unit test coverage

**File:** N/A (test gap)

**Problem:** No tests for duty cycle, comfort score, week-boundary, meter-reset.

**Fix:**
1. Add `tests/test_sensors_energy.py` (week boundary, meter reset, currency, BTU).
2. Add `tests/test_sensors_performance.py` (duty cycle, chatter, deque).
3. Add `tests/test_sensors_comfort.py` (score formula scaling).
4. Add `tests/test_sensors_health.py` (zone issues cap).

**Test:** Coverage report shows sensors >80%.

**Risk:** Low. Tests only.

**Depends on:** Issues fixes that change behavior (C06, C07, M02, M08, M09, etc.).

**Blocks:** none.
