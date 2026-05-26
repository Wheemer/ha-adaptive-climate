# Medium 31: Boost cap function of integral, not output headroom

**File:** `managers/setpoint_boost.py:147`

**Problem:** Cap `max(abs(integral) * 0.5, 15.0)` doesn't respect `out_max - E - F`. Overshoots clamp.

**Fix:**
1. Compute headroom: `headroom = (out_max - external - feedforward) - integral`.
2. Cap boost: `boost = min(delta * factor, headroom, max(abs(integral)*0.5, 15.0))`.
3. Use `boost_integral()` method from C03 fix (handles clamp).

**Test:** Unit: integral at upper bound, boost called, assert integral does not exceed bound.

**Risk:** Low.

**Depends on:** C03.

**Blocks:** none.
