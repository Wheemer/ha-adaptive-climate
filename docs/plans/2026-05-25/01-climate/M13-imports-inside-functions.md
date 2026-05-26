# Medium 13: imports inside functions without circular-import reason

**File:** `climate.py:32-37,1494,1496-1513`, `climate_control.py:14`

**Problem:** Many local imports (e.g. `from .const import PIDChangeReason`) inside functions. Half lack circular-import justification. Hides import failures.

**Fix:**
1. Audit each local import; identify which are truly required (circular).
2. Move all others to module top.
3. Comment remaining local imports with "circular: <module>".

**Test:** Module-level import + entity creation succeed; pyright clean.

**Risk:** Low.

**Depends on:** H14.

**Blocks:** none.
