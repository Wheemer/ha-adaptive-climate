# Low 18: protocol `_hvac_mode: HVACMode` should be `HVACMode | None`

**File:** `custom_components/adaptive_climate/protocols.py:133`

**Problem:** Entity initializes `_hvac_mode = None` at climate.py:549; protocol mismatches.

**Fix:** Update protocol type to `HVACMode | None`.

**Test:** Pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** A09.
