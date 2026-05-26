# Medium 10: `parse_sunset_offset` "≤12=hours, >12=minutes" surprising

**File:** `managers/night_setback_calculator.py:170-191`

**Problem:** Heuristic undocumented; raises `ValueError` on malformed input.

**Fix:**
1. Either deprecate bare-number form (require `h`/`m` suffix).
2. Or document explicitly in user docs + module docstring.
3. Wrap parse in try/except with clear log.

**Test:** Unit: malformed input → clear error not stack trace. Bare number → documented behavior.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Keep bare-number convenience or require explicit suffix?
