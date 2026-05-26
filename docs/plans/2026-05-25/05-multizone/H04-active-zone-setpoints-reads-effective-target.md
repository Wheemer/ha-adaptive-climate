# High 04: `get_active_zone_setpoints` returns night-setback-reduced target

**File:** `coordinator.py:521-533`

**Problem:** Reads climate entity's `temperature` attribute — which for adaptive zones is night-setback-reduced effective target. Auto mode switching median uses this, flipping mode to HEAT around setback boundaries even when daytime target fine.

**Fix:**
1. Store user setpoint (pre-setback) in `zone_data["user_target_temp"]`.
2. `get_active_zone_setpoints` reads from `zone_data`, not entity state.
3. Or read `target_temp_high` / configured preset target.
4. Move `HVACMode` import to module top (Med 03).

**Test:** Unit: zone with active night setback, assert returned setpoint is configured daytime value. Integration: auto-mode doesn't flip during setback window.

**Risk:** Med — requires zone_data plumbing from climate entity.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Should user_target_temp track preset changes or only manual `async_set_temperature` calls?
