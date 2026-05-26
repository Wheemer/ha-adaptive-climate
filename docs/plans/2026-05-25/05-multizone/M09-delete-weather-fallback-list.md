# Medium 09: Delete hard-coded weather fallback list

**File:** `managers/night_setback_calculator.py:114-122`

**Problem:** Hard-coded `weather.home`/`weather.knmi_home`/`weather.forecast_home` brittle.

**Fix:**
1. After C01 fix lands, delete fallback list.
2. Rely solely on `coordinator.weather_entity`.

**Test:** Unit: no weather_entity configured, assert returns None/empty cleanly.

**Risk:** Low.

**Depends on:** C01.

**Blocks:** none.
