# Arch 05: Coordinator doing too much — decompose

**File:** `coordinator.py`

**Problem:** Zone registry, EMA filter, solar-gain helper, mode-sync, auto-mode dispatch, manifold facade, sun position, central-controller wiring all in one file.

**Fix:**
1. Extract `ModeSync` (M06).
2. Extract `SunPositionCalculator` wrapper to `solar/sun_position.py` (if not already).
3. Extract solar-gain helper to `solar/solar_gain_helper.py`.
4. Extract manifold facade to `managers/manifold_registry.py`.
5. Keep coordinator focused on zone registry + DataUpdateCoordinator contract.

**Test:** Existing tests pass. `wc -l coordinator.py` < 800.

**Risk:** Med — large move set; verify no circular imports.

**Depends on:** M06.

**Blocks:** none.
