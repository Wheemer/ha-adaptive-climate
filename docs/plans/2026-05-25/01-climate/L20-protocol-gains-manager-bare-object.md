# Low 20: `_gains_manager` typed as bare `object`

**File:** `custom_components/adaptive_climate/protocols.py:427`

**Problem:** `_gains_manager(self) -> object`.

**Fix:** Add TYPE_CHECKING import + annotate `-> PIDGainsManager`.

**Test:** Pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** A09.
