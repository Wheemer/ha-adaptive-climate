# Low 14: format_iso8601 trivial wrapper

**File:** `managers/status_manager.py:181-190`

**Problem:** One-line `.isoformat()` wrapper. Inline or enforce UTC.

**Fix:**
1. Make it enforce UTC: `dt.astimezone(UTC).isoformat()`.
2. Or inline at call sites.

**Test:** Unit: pass local dt, assert output ends `+00:00`.

**Risk:** Low.

**Depends on:** M15.

**Blocks:** none.
