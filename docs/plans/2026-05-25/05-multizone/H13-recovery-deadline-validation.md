# High 13: `recovery_deadline` parsed without validation

**File:** `managers/night_setback_calculator.py:285-289`

**Problem:** `hour, minute = map(int, deadline.split(":"))`. Malformed `"7:00am"` → runtime ValueError in logs only, not actionable config error.

**Fix:**
1. Validate `recovery_deadline` at config-flow / `climate_setup.py` via regex `^([01]?\d|2[0-3]):[0-5]\d$`.
2. Or wrap parse in try/except, `_LOGGER.error` with zone id, fallback to `07:00`.
3. Add schema voluptuous validator.

**Test:** Unit: malformed deadline, assert config error raised at setup (not later). Valid deadline parses correctly.

**Risk:** Low.

**Depends on:** none.

**Blocks:** M11.
