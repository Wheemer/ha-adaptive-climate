# Low 16: unused imports in `__init__.py`

**File:** `custom_components/adaptive_climate/__init__.py:7`

**Problem:** `datetime`, `timedelta`, `typing.Any` imported but unused outside stubs.

**Fix:**
1. Run ruff check; remove unused.

**Test:** Ruff clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
