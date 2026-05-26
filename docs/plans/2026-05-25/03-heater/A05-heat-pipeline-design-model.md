# Architectural 05: HeatPipeline uses linear committed-heat model — physically wrong

**File:** `managers/heat_pipeline.py`

**Problem:** Linear interpolation valve_open → valve_closed+transport_delay. Real hydronic has exponential rise/decay matched to thermal mass.

**Fix:**
1. Only relevant if C01 = WIRE.
2. Model as exponential rise/decay using thermal time constant `tau`.
3. Parameterize per heating type (floor: long tau; radiator: medium; convector: short).

**Test:** Compare predicted vs actual cycle overshoot reduction across heating types.

**Risk:** High — physics modeling, calibration needed.

**Depends on:** C01.

**Blocks:** none.

**Unresolved:** Calibration data source? May require user opt-in instrumented logging.
