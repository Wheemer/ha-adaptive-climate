# Low 41: `reset_clamp_state` has no caller; `was_clamped` permanently sticky

**File:** `pid_controller/__init__.py:276-283`

**Problem:** `was_clamped` becomes sticky-true forever once tripped.

**Fix:**
1. `grep -r reset_clamp_state custom_components/` to confirm zero callers.
2. If unused: delete method + flag, or wire into `CycleTrackerManager` on cycle start.
3. Prefer wire-up: reset on IDLE→HEATING transition.

**Test:** Unit: confirm reset fires on cycle start; was_clamped reflects current cycle.

**Risk:** Low.

**Depends on:** none. Related to `03-heater/<cycle-tracker>` event coupling.

**Blocks:** none.
