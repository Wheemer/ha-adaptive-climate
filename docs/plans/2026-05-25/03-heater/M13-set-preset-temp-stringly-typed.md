# Medium 13: async_set_preset_temp uses stringly-typed magic substrings

**File:** `managers/temperature_manager.py:299-333`

**Problem:** `"disable" in preset_name` — preset named `comfort_temp_disable` works coincidentally; `comfort_temp` + disable-flag doesn't compose.

**Fix:**
1. Define enum or split into dedicated methods per preset (`set_comfort_temp`, `disable_comfort_temp`).
2. Remove magic-substring matching.
3. Migrate callers.

**Test:** Unit test each preset set/disable path explicitly.

**Risk:** Low-Med — touches public API; check service/UI callers.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Are there external service callers using the legacy string form? If so, keep deprecated alias.
