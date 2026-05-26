# Critical 03: coordinator `__init__` reads domain data before populated

**File:** `coordinator.py:46`

**Problem:** `SunPositionCalculator.from_hass(hass)` runs sync in event loop. `__init__` touches `hass.states.get(weather_entity_id)` (via `outdoor_temp`) and `hass.data.get(DOMAIN, {}).get("house_energy_rating")` **before** `__init__.py` populates those keys on cold start. Result: fresh install gets `_outdoor_temp_tau = 4.0` regardless of user `A++` config, and `_outdoor_temp_lagged = None`.

**Fix:**
1. Audit `__init__.py` to confirm population order.
2. Move EMA-tau resolution and initial lag-temp seeding into `async_setup()` / first-update method (not `__init__`).
3. Audit `SunPositionCalculator.from_hass` for blocking I/O; defer if needed.
4. Document required initialization order in coordinator docstring.

**Test:** Integration: fresh install with `house_energy_rating: A++`, assert `_outdoor_temp_tau` matches A++ value. Unit: instantiate coordinator with empty `hass.data`, assert no KeyError + defaults applied.

**Risk:** Med — refactor of init path.

**Depends on:** none.

**Blocks:** H02 (EMA seeding).
