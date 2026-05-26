# Architectural 09: Pyright strict on adaptive/ source

**File:** `adaptive/learning.py:352` + module-wide

**Problem:** `HVACMode = None` defaults rely on TYPE_CHECKING; pyright strict behavior unclear.

**Fix:**
1. Run pyright strict on `adaptive/`; capture errors.
2. Fix each (string forward-refs, runtime imports, type: ignore[specific]).
3. Add to CI gate.
4. Document policy in CLAUDE.md.

**Test:** Pyright strict clean; CI enforces.

**Risk:** Low — may surface many small issues.

**Depends on:** L02.

**Blocks:** none.
