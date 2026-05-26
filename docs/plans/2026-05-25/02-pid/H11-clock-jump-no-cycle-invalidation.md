# High 11: Clock jump silently clamps dt; cycle tracker keeps accumulating

**File:** `managers/control_output.py:148-159`

**Problem:** Negative/huge dt → `actual_dt=0` passes through. PID first-call branch handles it, but CycleMetricsRecorder continues stats across sleep/resume gap.

**Fix:**
1. When clamp fires, dispatch `clock_jump` event via existing event dispatcher.
2. `CycleTrackerManager` subscribes; on event, invalidate in-flight cycle (`_cycle_active = False`, no metrics recorded).
3. Add `clock_jumps_detected` counter to debug state attributes (also fixes L36).

**Test:** Integration: simulate suspend (monotonic jump), assert in-flight cycle marked invalid.

**Risk:** Med. Cross-module event coupling; ensure no listener leak.

**Depends on:** none.

**Blocks:** L36 (counter exposure).

**Unresolved:** Use existing `CycleEventDispatcher` or new bus? Confirm with `03-heater/H22` (similar event coupling).
