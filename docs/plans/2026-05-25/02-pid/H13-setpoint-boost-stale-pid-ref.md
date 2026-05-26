# High 13: Setpoint boost callback can mutate stale PID on reload

**File:** `managers/setpoint_boost.py:105,172-177`

**Problem:** `_apply_boost` references `self._pid`; on integration reload, old PID is stale. Missed `cancel()` → callback mutates GC'd object.

**Fix:**
1. Add `_destroyed: bool = False` flag, set in `cancel()`.
2. Guard `_apply_boost` entry: `if self._destroyed or not self._enabled: return`.
3. Wrap mutation in try/except logging; do not raise from scheduled callback.

**Test:** Unit: cancel boost mid-debounce, assert callback no-ops.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
