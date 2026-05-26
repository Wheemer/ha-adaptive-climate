# Low 08: hvac_mode == "heat" StrEnum stringification ambiguity

**File:** `managers/cycle_metrics.py:484-490`

**Problem:** Same ambiguity as M01.

**Fix:**
1. Use `HVACMode.HEAT` enum for comparison.
2. Resolve consistently with M01 strategy.

**Test:** Same as M01.

**Risk:** Low.

**Depends on:** M01 (apply same convention).

**Blocks:** none.
