# High 12: Legacy history restore silently zeros Ke

**File:** `managers/pid_gains_manager.py:88,357-364`

**Problem:** `restore_from_history` with legacy entry (no `ke` field) gets `ke=None` → `replace()` substitutes current; migration fills `ke=0.0`. Risk of unexpected Ke=0 transition with no debug trace.

**Fix:**
1. In `_migrate_history_entry`, when ke missing, preserve current ke instead of 0.0.
2. Log debug when ke restored from legacy entry: `"ke restored as %s for legacy entry %d"`.
3. Add unit test covering legacy entry round-trip.

**Test:** Unit: restore_from_history with entry lacking `ke`, assert current ke preserved.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
