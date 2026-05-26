# Low 05: `_outdoor_temp_unsub` missing type annotation

**File:** `coordinator.py:53-57`

**Problem:** `_outdoor_temp_unsub: Any = None` missing proper annotation.

**Fix:**
1. Use `CALLBACK_TYPE | None`.
2. Import from `homeassistant.core`.

**Test:** Pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
