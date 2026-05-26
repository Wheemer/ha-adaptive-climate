# Critical 02: `check_auto_apply_limits` compares ISO string > datetime

**File:** `adaptive/validation.py:182-186`

**Problem:** `entry.get("timestamp", now) > cutoff` compares ISO `str` (from `pid_gains_manager.py:168`) against `datetime` → TypeError. Masked because callers pass `pid_history=[]` (`learning.py:617, 1359`); MAX_AUTO_APPLIES_PER_SEASON gate currently no-op.

**Fix:**
1. Parse `entry["timestamp"]` via `datetime.fromisoformat(...)` ensuring tz-aware (`dt_util.parse_datetime` or check `tzinfo`).
2. Wrap in try/except (`ValueError`, `TypeError`); skip malformed entries with WARN log.
3. Use `dt_util.utcnow()` for `now` when entry has no timestamp.
4. Re-wire real `pid_history` at call sites `learning.py:617` and `learning.py:1359` (pull from `pid_gains_manager.get_history(mode)`).

**Test:** Unit: feed mixed history (ISO strings, missing ts, malformed) → no crash, correct seasonal count. Integration: auto-apply 5x in 90d → 6th blocked.

**Risk:** Med — un-masks a path that was effectively dead. Verify gate count semantics.

**Depends on:** none.

**Blocks:** C03 (uses pid_history properly).
