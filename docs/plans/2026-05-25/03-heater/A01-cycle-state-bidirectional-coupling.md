# Architectural 01: Bidirectional cycle-state coupling between HeaterController and CycleTrackerManager

**File:** `managers/heater_controller.py`, `managers/cycle_tracker.py`

**Problem:** Two independent state machines for one logical cycle, sync'd only by event ordering. Race-prone.

**Fix:**
1. Make `CycleTrackerManager` sole owner of "is cycle active?" state.
2. `HeaterController` queries tracker via Protocol method (`is_cycle_active(mode)`) instead of own `_cycle_active`.
3. Tracker's state machine becomes single source of truth.
4. Remove `_cycle_active` from HeaterController.

**Test:** Race tests covering rapid transitions, concurrent timers.

**Risk:** High — touches core state machine; large blast radius.

**Depends on:** H01, C03, H04, M08 (stabilize state machine fixes first).

**Blocks:** none.

**Unresolved:** Performance impact of indirect lookup on every emit decision?
