# High 10: duty accumulator reset uses magic `0.5` °C threshold

**File:** `custom_components/adaptive_climate/climate.py:1755`

**Problem:** `abs(value - old_temp) > 0.5` hardcoded; inconsistent with recovery threshold 0.3 elsewhere (climate_control.py:238).

**Fix:**
1. Add `DUTY_ACCUMULATOR_RESET_THRESHOLD` to const.py.
2. Make heating-type-aware via existing threshold table.
3. Replace literal; cross-reference cycle reset rules to align.

**Test:** Unit: per heating type, accumulator reset triggers at type-correct threshold.

**Risk:** Low.

**Depends on:** none.

**Blocks:** A10.
