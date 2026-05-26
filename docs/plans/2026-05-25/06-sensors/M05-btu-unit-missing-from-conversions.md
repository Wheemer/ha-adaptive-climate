# Medium 05: BTU missing from UNIT_CONVERSIONS produces 3412x error

**File:** `sensors/energy.py:545-548` + `analytics/energy.py:9-13`

**Problem:** `UNIT_CONVERSIONS` has GJ/KWH/MWH/WH. BTU mentioned in docs but missing → falls back to 1.0× → massive scaling error.

**Fix:**
1. Add `BTU` → kWh conversion (1 BTU = 0.000293071 kWh).
2. Add `THERM`, `MMBTU` for gas utility meters.
3. Raise ValueError (not silent fallback) on unknown unit.

**Test:** Unit: convert 10000 BTU; assert ~2.93 kWh. Unknown unit → ValueError.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
