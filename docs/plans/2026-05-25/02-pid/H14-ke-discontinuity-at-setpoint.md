# High 14: Ke external term steps to 0 at setpoint crossing

**File:** `pid_controller/__init__.py:582-585`

**Problem:** `if self._error >= 0: external = Ke*dext else: 0`. Instantaneous drop creates output step exactly at setpoint roll-off.

**Fix:**
1. Replace hard gate with smooth scaling: `gate = max(0.0, min(1.0, error / cold_tolerance + 1))`; `external *= gate`.
2. Alternative: apply unconditionally and let integral compensate.
3. Document choice in docstring (also fixes Architectural #5).
4. Add unit test for continuity across setpoint crossing.

**Test:** Unit: sweep error -1°C → +1°C, assert no output step > 0.5%.

**Risk:** Med. Behavioral change; affects all users with Ke>0.

**Depends on:** none.

**Blocks:** L40, A05.

**Unresolved:** Smooth-scale tolerance band — `cold_tolerance` from config or fixed 0.5°C?
