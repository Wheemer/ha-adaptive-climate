# Architectural 08: `parameters` dict (60+ fields) needs typed dataclass

**File:** `custom_components/adaptive_climate/climate_setup.py:237-324`

**Problem:** Grew organically; kwargs unpacking into entity `__init__` defeats type checking.

**Fix:**
1. Define `AdaptiveThermostatConfig` dataclass with strict types.
2. Build from schema in `async_setup_platform`, validated once.
3. Entity `__init__(config: AdaptiveThermostatConfig)`; access fields via `config.xxx`.

**Test:** Pyright strict; existing tests adapted.

**Risk:** Med — large interface change.

**Depends on:** C04 (wire all configs first).

**Blocks:** none.
