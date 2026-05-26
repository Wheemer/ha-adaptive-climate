# Low 37: `restore_from_history` empty-history message misleading

**File:** `managers/pid_gains_manager.py:347-348`

**Problem:** Includes `index` (may be valid 0) in error message about empty history.

**Fix:**
1. Branch: if history empty, raise `ValueError("Cannot restore: PID history is empty")`.
2. Else (out-of-range): raise `ValueError(f"Invalid history index {index}; have {len(history)} entries")`.

**Test:** Unit: empty history vs out-of-range, assert distinct messages.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
