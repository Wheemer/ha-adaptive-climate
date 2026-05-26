# High 02: EMA resets to raw temp when `dt_seconds=0`

**File:** `coordinator.py:611-614`

**Problem:** `dt_seconds=0` triggers `update_outdoor_temp_lagged` `dt <= 0` branch which overwrites `_outdoor_temp_lagged`. Happens on first update after restart (acceptable) but also when two events arrive same monotonic tick (HA replay) — loses history.

**Fix:**
1. When `_last_outdoor_temp_update is None`: seed EMA without running filter.
2. Else: clamp `dt = max(dt_seconds, MIN_DT)` so zero-dt is no-op, not reset.
3. Add `MIN_DT = 1.0` constant.
4. Unit test for both paths.

**Test:** Unit: simulate two same-tick events, assert EMA preserves history. First update post-restart, assert seeding.

**Risk:** Low.

**Depends on:** C03.

**Blocks:** none.
