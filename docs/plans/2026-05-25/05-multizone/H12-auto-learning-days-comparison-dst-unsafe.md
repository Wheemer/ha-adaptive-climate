# High 12: `(current - last).days > 0` breaks on DST/negative delta

**File:** `managers/night_setback_manager.py:261`

**Problem:** `timedelta.days` on sub-24h positive = 0 (intended). But DST or local-time persistence can make delta negative → `.days == -1` → `> 0` False → silently skips activation log.

**Fix:**
1. Use UTC throughout (`dt_util.utcnow()`).
2. Compare via `(current - last).total_seconds() > 86400`.
3. Or use explicit cooldown_seconds constant.

**Test:** Unit: simulate DST jump backward, assert activation still respects cooldown correctly.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
