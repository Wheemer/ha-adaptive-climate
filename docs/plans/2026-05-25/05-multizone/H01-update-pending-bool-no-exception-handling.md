# High 01: `_update_pending` stuck True if `async_create_task` raises

**File:** `coordinator.py:50, 372-375`

**Problem:** No try/except around scheduling. If `async_create_task` raises (HA shutdown), flag stays True forever, no further central updates fire.

**Fix:**
1. Wrap `async_create_task` in try/except.
2. Reset `_update_pending = False` in except.
3. Log warning.
4. Or fold into rerun-pending pattern (C04).

**Test:** Unit: mock `async_create_task` to raise, assert flag reset.

**Risk:** Low.

**Depends on:** C04.

**Blocks:** none.
