# Low 02: Unused re-exports in sensor.py

**File:** `sensor.py:18-40`

**Problem:** Re-imports symbols already exposed via `sensors/__init__.py`. Pyright flags unused.

**Fix:**
1. Remove duplicate imports from `sensor.py`.

**Test:** Pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
