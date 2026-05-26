# Medium 05: Redeclared attribute annotation in `else` branch

**File:** `coordinator.py:43-80` (line 64)

**Problem:** Pyright flags redeclaration: line 62 sets attribute, line 64 re-annotates inside `else`.

**Fix:**
1. Move annotation to class body or first assignment.
2. Remove inline annotation from `else`.

**Test:** `pyright custom_components/adaptive_climate/coordinator.py` clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
