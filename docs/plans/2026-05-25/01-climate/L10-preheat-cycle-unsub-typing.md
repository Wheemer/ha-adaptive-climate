# Low 10: `_preheat_cycle_unsub` lacks type annotation

**File:** `custom_components/adaptive_climate/climate.py:402-403`

**Problem:** Implicit type from assignment.

**Fix:** Annotate `self._preheat_cycle_unsub: Callable[[], None] | None = None`.

**Test:** Pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
