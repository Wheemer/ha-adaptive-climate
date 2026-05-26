# Architectural 09: protocols.py exposes ~30 properties — defeats Protocol purpose

**File:** `custom_components/adaptive_climate/protocols.py`

**Problem:** Protocol = documentation of entity, not interface. Most managers only need `_current_temp`, `_target_temp`, `_hvac_mode`.

**Fix:**
1. Audit each manager: list properties/methods actually called.
2. Define small role-based protocols (`TemperatureState`, `PIDState`, `HVACState`, `LearningState`).
3. Manager constructors accept the minimal protocol they need.
4. Delete bloat from `ThermostatState`.

**Test:** Pyright strict; managers compile against narrow protocols only.

**Risk:** Med-High.

**Depends on:** A02 (commit to Protocol first), L18, L19, L20.

**Blocks:** none.
