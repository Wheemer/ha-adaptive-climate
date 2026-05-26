# High 09: HEATING_TYPE_CHARACTERISTICS max_settling_time unused

**File:** `managers/cycle_tracker.py:128-144`

**Problem:** Constructor receives `heating_type` and `HEATING_TYPE_CHARACTERISTICS[ht]["max_settling_time"]` exists (const.py:239: 90/60/30/20 min), but `_max_settling_time_minutes` derived only from `thermal_time_constant` or generic 120-min default. Floor systems w/o `area_m2` (no tau) get 120 min — too short for hydronic.

**Fix:**
1. When both `settling_timeout_minutes` and `thermal_time_constant` are None, use `HEATING_TYPE_CHARACTERISTICS[heating_type]["max_settling_time"]`.
2. Add fallback chain: explicit config → tau-derived → heating-type table → generic 120-min.

**Test:** Unit test floor_hydronic without area_m2 — assert settling timeout ≥ 90 min.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
