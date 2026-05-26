# High 15: `_time_below_target` never decayed within tolerance

**File:** `adaptive/undershoot_detector.py:298-308`

**Problem:** Only reset on temp ABOVE setpoint. System within tolerance forever accumulates time → stale counter retriggers boost.

**Fix:**
1. Reset `_time_below_target` when temp within `cold_tolerance` for some duration (e.g. 30 min).
2. Or: continuous decay (`*= exp(-dt / tau)` with tau ~ 1h).
3. Also reset `_thermal_debt` on same condition.

**Test:** Unit: hold temp at tolerance for 1h → counter decays/resets; subsequent below-target accumulation starts from 0.

**Risk:** Med — affects undershoot trigger frequency.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Decay (smooth) vs reset (sharp)? hvac-expert opinion.
