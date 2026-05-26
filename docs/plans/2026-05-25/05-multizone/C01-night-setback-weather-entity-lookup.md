# Critical 01: night_setback_calculator reads non-existent `_weather_entity`

**File:** `managers/night_setback_calculator.py:112-114`

**Problem:** `get_weather_condition()` reads `coordinator._weather_entity` which doesn't exist; coordinator exposes a `weather_entity` property. First branch always False; silently falls back to hard-coded `weather.home`/`weather.knmi_home`/`weather.forecast_home`. Dynamic recovery-end calc broken for any user with a differently-named weather entity.

**Fix:**
1. Replace `coordinator._weather_entity` with `coordinator.weather_entity` (guard `None`).
2. Inject weather_entity_id via `__init__` (or read from injected coordinator) — stop reaching into `hass.data`.
3. Delete fallback list `weather.home`/`weather.knmi_home`/`weather.forecast_home` (see M07).

**Test:** Unit: mock coordinator with custom `weather_entity` value, assert `get_weather_condition()` reads it. Integration: configure non-default weather entity, verify night setback end time derives from forecast.

**Risk:** Low — straightforward attribute fix.

**Depends on:** none.

**Blocks:** M07.
