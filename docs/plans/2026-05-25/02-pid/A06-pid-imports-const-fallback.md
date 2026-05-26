# Architectural 6: PID try/except fallback for `const.py` constants

**File:** `pid_controller/__init__.py` (imports section)

**Problem:** Fallback values diverge from `const.py` if updated. Controller is HA-only — fallback unnecessary.

**Fix:**
1. Remove try/except around `INTEGRAL_DECAY_THRESHOLDS`, `HEATING_TYPE_CHARACTERISTICS` imports.
2. Hard-require const.py imports.
3. Or extract shared `defaults.py` if cross-process portability matters (it doesn't).

**Test:** Module imports; tests pass.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
