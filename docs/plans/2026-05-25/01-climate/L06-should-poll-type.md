# Low 06: `should_poll` lacks bool annotation

**File:** `custom_components/adaptive_climate/climate.py:840`

**Problem:** `def should_poll(self): return False`.

**Fix:** Annotate `-> bool`.

**Test:** Pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
