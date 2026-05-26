# Architectural 03: setter callback pattern (`_set_p`, `_set_i`, ...) is busy-work indirection

**File:** `custom_components/adaptive_climate/climate.py` (setters 1663-1738)

**Problem:** Each manager handed closure to one-line host setter. Workaround for not passing `self`, but `self` is passed to HeaterController, ControlOutputManager etc anyway.

**Fix:**
1. Pick one: typed Protocol facade OR pass `self` with defined ABC/Protocol.
2. Remove closure registration; managers call `state.set_p(...)` directly via Protocol.
3. Delete one-line setters.

**Test:** Pyright clean; integration tests unaffected.

**Risk:** Med-High.

**Depends on:** A02, H02.

**Blocks:** none.
