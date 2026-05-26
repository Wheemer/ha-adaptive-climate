# Medium 02: <1min cycle drop threshold not heating-type-aware

**File:** `sensors/performance.py:472`

**Problem:** Cycles <1.0min silently dropped. Hides legitimate 30s valve pulses on relay-controlled systems.

**Fix:**
1. Make threshold depend on heating_type (e.g., 0.5min for radiator/valve, 1.0min for forced_air).
2. Pull from HEATING_TYPE config.

**Test:** Unit: radiator + 45s cycle; assert kept.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
