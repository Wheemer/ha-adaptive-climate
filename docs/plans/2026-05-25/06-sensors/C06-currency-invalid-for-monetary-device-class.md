# Critical 06: Currency parsed from UoM is invalid for MONETARY

**File:** `sensors/energy.py:495-497, 526-528`

**Problem:** `WeeklyCostSensor.native_unit_of_measurement` returns parsed currency like `"$"`. `SensorDeviceClass.MONETARY` requires ISO 4217 code (USD/EUR/GBP). HA emits validation warning, may drop from recorder.

**Fix:**
1. Maintain symbol→ISO map (`$`→`USD`, `€`→`EUR`, `£`→`GBP`, etc.).
2. Validate parsed currency against ISO 4217 set; fallback to `USD` with warning.
3. If unmappable, drop `device_class=MONETARY` (use plain numeric sensor).

**Test:** Unit: parse `"$/kWh"`, `"€"`, `"USD/MWh"`, `"unknown"`; assert valid ISO or device_class cleared.

**Risk:** Med. Historical statistics may need re-init.

**Depends on:** none.

**Blocks:** M04 (currency drift on update).
