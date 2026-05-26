# Medium 12: `consume_transition` single-shot read

**File:** `managers/night_setback_manager.py:382-392`

**Problem:** Second consumer never sees transition.

**Fix:**
1. Document single-consumer contract in method docstring.
2. Or fan out via `CycleEventDispatcher` with new `NightSetbackTransitionEvent`.

**Test:** Unit: assert documented behavior (or fan-out delivery).

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Document single-consumer or upgrade to event bus?
