# Low 12: Solar threshold unit ambiguity

**File:** `adaptive/disturbance_detector.py:106-119`

**Problem:** `solar_increase > 100` — comment says "W/m² or lux"; threshold same → lux misfires.

**Fix:**
1. Read sensor `unit_of_measurement` from HA state.
2. Branch: lux threshold = 1000, W/m² = 100.
3. Or document required unit + validate on init.

**Test:** Unit: lux sensor with reading 500 → no trigger; W/m² sensor 150 → trigger.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Auto-detect units vs require config?
