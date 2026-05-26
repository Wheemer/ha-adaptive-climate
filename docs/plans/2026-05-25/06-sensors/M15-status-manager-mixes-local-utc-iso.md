# Medium 15: status_manager mixes local + UTC timestamps in same payload

**File:** `managers/status_manager.py:223`

**Problem:** `dt_util.now()` (local) elsewhere `dt_util.utcnow()` (UTC). Mixed offsets in `status.overrides`.

**Fix:**
1. Use `dt_util.utcnow()` consistently.
2. Audit all `format_iso8601` call sites.
3. Make `format_iso8601` enforce UTC via `astimezone(UTC)`.

**Test:** Unit: assert all override timestamps end with `+00:00`.

**Risk:** Low.

**Depends on:** none.

**Blocks:** L14 (format_iso8601 inline/enforce).
