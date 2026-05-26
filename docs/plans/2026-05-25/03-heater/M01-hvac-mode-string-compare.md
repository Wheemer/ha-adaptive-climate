# Medium 01: hvac_mode string compare in _on_cycle_started

**File:** `managers/cycle_tracker.py:354-359`

**Problem:** `event.hvac_mode == "heat"`. Event typed as `str` but HeaterController emits `HVACMode.HEAT` (StrEnum). Works today, typing claim wrong.

**Fix:**
1. Either normalize at emit time: `hvac_mode=str(hvac_mode)`.
2. Or retype event field as `HVACMode | str` and compare via enum.
3. Pick one consistently across event payloads.

**Test:** Unit test event compares both raw string and HVACMode enum.

**Risk:** Low.

**Depends on:** none.

**Blocks:** L07 (same pattern in cycle_metrics).
