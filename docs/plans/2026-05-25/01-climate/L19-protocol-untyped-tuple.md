# Low 19: protocol `_calculate_night_setback_adjustment -> tuple` untyped

**File:** `custom_components/adaptive_climate/protocols.py:353`

**Problem:** Bare `tuple`.

**Fix:** Annotate `-> tuple[float | None, bool, dict]`.

**Test:** Pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** A09.
