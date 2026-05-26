# Low 17: `TemperatureState` Protocol exposes underscore attrs

**File:** `protocols.py:34-58`

**Problem:** `_ext_temp` / `_cold_tolerance` on public Protocol leaks impl details, prevents alternative implementations.

**Fix:**
1. Add public properties (`ext_temp`, `cold_tolerance`) to Protocol.
2. Keep underscore attrs as backing storage on entity.
3. Update all consumers to use public names.

**Test:** Pyright clean. Existing tests pass.

**Risk:** Low — refactor scope manageable.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Cross-stream coordination — same Protocol used by climate/PID streams?
