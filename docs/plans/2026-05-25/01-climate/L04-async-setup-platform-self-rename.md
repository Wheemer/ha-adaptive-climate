# Low 04: `async_setup_platform as async_setup_platform` self-rename

**File:** `custom_components/adaptive_climate/climate.py:78-79`

**Problem:** Self-rename for re-export; ugly.

**Fix:**
1. Remove `as` alias.
2. Add `__all__ = ["async_setup_platform", "PLATFORM_SCHEMA"]` at top.

**Test:** Import paths from outside still work.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
