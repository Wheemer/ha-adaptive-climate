# High 05: _cycle_active / _has_demand not persisted across restart

**File:** `managers/heater_controller.py:160-161`, `climate.py` state restore

**Problem:** Reset to False every `__init__`. After HA restart mid-cycle while heater ON: control tick → CYCLE_STARTED → CycleTrackerManager.reset_cycle_metrics wipes restored device-on/off timestamps → metrics restart from `now`, not original start. In-progress cycle's clamp/integral observations lost.

**Fix:**
1. Persist `_cycle_active`, `_cycle_start_time`, `_has_demand` via `extra_state_attributes`.
2. Restore on `async_added_to_hass`.
3. On restore with active cycle: mark cycle as "discard for learning" (skip metrics row for partial slice) OR rebuild from persisted timestamps.
4. Document chosen approach in code + CLAUDE.md.

**Test:** Restart simulation mid-cycle → assert no spurious CYCLE_STARTED, metrics row either skipped or uses original timestamp.

**Risk:** Med — restoration semantics affect learning data.

**Depends on:** none.

**Blocks:** `04-learning` cycle_count persistence concerns (cross-ref).

**Unresolved:** Discard partial cycle vs rebuild? Recommend discard (simpler, no false data).
