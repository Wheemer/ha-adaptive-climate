# Critical 07: `_cancel_*_startup_unlocked` releases lock mid-method

**File:** `central_controller.py:229-267`

**Problem:** Methods named `_unlocked` (caller holds lock) actually release + re-acquire to avoid deadlock with task `finally`. Three races: (1) invariants violated across release, (2) concurrent `update()` sees stale `_heater_waiting_for_startup=True` and bails, (3) cancelled task acquires lock and runs `_turn_on_switches` for stale demand.

**Fix:**
1. Refactor: snapshot task ref → release lock → cancel + await task → reacquire → clear state fields.
2. Or eliminate lock dance: check-then-act under lock + `asyncio.shield` outside lock.
3. Rename method to reflect actual locking behavior.
4. Add `_closed` flag on controller; delayed task body checks before re-acquiring (see H11).

**Test:** Unit: stress test concurrent demand changes during startup cancellation; assert no stale switch-on. Add asyncio fault injection.

**Risk:** High — touches critical concurrency path; potential for deadlock if mis-refactored.

**Depends on:** none.

**Blocks:** H07, H11.
