# High 05: `forecast_hours` alias drops falsy zero values

**File:** `managers/auto_mode_switching.py:53`

**Problem:** `or` chain collapses 0/`""` to default. Also alias name misleading: value used as days on line 164 (`forecast[: self._forecast_days]`).

**Fix:**
1. Use explicit `if x is not None` for alias resolution.
2. Either drop legacy `forecast_hours` alias, or convert hours→days when reading.
3. Document in config schema.
4. Deprecation warning if legacy key used.

**Test:** Unit: config with `forecast_hours: 0`, assert respected (not default). Config with both keys, assert primary wins.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Drop alias entirely or keep with hours→days conversion?
