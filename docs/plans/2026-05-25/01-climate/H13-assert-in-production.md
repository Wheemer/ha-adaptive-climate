# High 13: `assert platform` in production code (stripped by python -O)

**File:** `custom_components/adaptive_climate/climate_setup.py:204`

**Problem:** CLAUDE.md forbids `assert` in production. `python -O` strips → AttributeError on None platform.

**Fix:**
1. Replace with `if platform is None: raise RuntimeError("platform not initialized")`.
2. Grep entire `custom_components/` for other production asserts; replace all.

**Test:** Unit: pass None platform → RuntimeError.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
