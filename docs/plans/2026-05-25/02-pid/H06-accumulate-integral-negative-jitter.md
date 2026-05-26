# High 6: `_accumulate_integral` boundary math can subtract integral on jitter

**File:** `pid_controller/__init__.py:475-480`

**Problem:** `time_in_dead` and `time_normal` can briefly go negative when monotonic-elapsed mixes with sensor-derived `_dt`. A single jittery sample subtracts integral.

**Fix:**
1. Clamp: `time_in_dead = max(0.0, transport_delay_seconds - (elapsed_seconds - self._dt))`.
2. Clamp: `time_normal = max(0.0, self._dt - time_in_dead)`.
3. Add debug log when clamped (indicates upstream timing drift).

**Test:** Unit: feed inconsistent dt vs elapsed, assert integral never decreases due to math.

**Risk:** Low. Defensive.

**Depends on:** none.

**Blocks:** none.
