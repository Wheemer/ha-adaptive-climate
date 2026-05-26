# Architectural 03: Sensors read peers via hass.states.get(f"sensor...")

**File:** Multiple (`comfort.py`, `energy.py`, `health.py`, `scheduled.py`)

**Problem:** Hidden runtime dependency graph; brittle on rename.

**Fix:**
1. Maintain `SensorRegistry` on coordinator: zone_id → {comfort: instance, energy: instance, ...}.
2. Sensors register on async_added_to_hass, unregister on remove.
3. Cross-sensor reads call methods directly, not via state lookups.
4. Remove all `f"sensor.{zone_id}_..."` lookups.

**Test:** Integration: rename entity; assert all cross-reads still work.

**Risk:** High. Many call sites + coordinator changes.

**Depends on:** H08 (preliminary fix).

**Blocks:** none.
