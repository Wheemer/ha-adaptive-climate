# Low 15: `helpers/registry.py` swallows ImportError, NameError later

**File:** `helpers/registry.py:6-15`

**Problem:** `try/except ImportError: pass`; later refs `er`/`ar`/`fr` raise `NameError` in tests.

**Fix:**
1. Define fallback names in `except` block (assign None or shim).
2. Or remove fallback entirely if HA always available.

**Test:** Test import without HA, assert clear failure mode.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
