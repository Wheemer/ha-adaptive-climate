# Medium 20: `_migrate_history_entry` defaults missing gains to 0.0

**File:** `managers/pid_gains_manager.py:279-296`

**Problem:** Malformed entry missing kp gets `kp=0.0`. If user targets that index via `restore_from_history`, PID becomes dead.

**Fix:**
1. When required field (kp/ki/kd) missing, skip entry entirely (return None).
2. Or fall back to current gains for missing field.
3. Log warning with entry index + missing field.
4. Filter None-returning entries from migrated history.

**Test:** Unit: migrate entry without kp, assert entry skipped + warning logged.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
