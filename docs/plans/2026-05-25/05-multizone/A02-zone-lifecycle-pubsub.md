# Arch 02: Zone lifecycle events via CycleEventDispatcher

**File:** `coordinator.py` (zone register/unregister)

**Problem:** `ModeSync`, `CentralController`, `ThermalGroupManager` not consistently notified on zone lifecycle events.

**Fix:**
1. Add `ZoneRegisteredEvent`/`ZoneUnregisteredEvent` to `events.py`.
2. Coordinator emits on register/unregister.
3. Subscribers (ModeSync, CentralController, ThermalGroupManager) listen.
4. Remove ad-hoc plumbing in `unregister_zone`.

**Test:** Unit: register/unregister, assert all subscribers notified. Integration: reload, no stale state.

**Risk:** Med — touches multiple managers.

**Depends on:** M13.

**Blocks:** H10.
