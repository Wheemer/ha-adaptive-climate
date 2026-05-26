# Architectural 3: Sampling-period vs event-driven bifurcation in `PID.calc()`

**File:** `pid_controller/__init__.py:519-537`

**Problem:** Two code paths for `_input_time`. Sampling-period is legacy/dead; event-driven is what `ControlOutputManager` uses.

**Fix:**
1. Grep all callers of `calc()` — confirm sampling-period mode unused.
2. If unused: delete sampling-period branch; keep only event-driven (input_time passed in).
3. If used: ensure monotonic (already from C01).

**Test:** All PID tests pass with single path.

**Risk:** Med. Behavioral change if any caller relied on sampling mode.

**Depends on:** C01.

**Blocks:** none.

**Unresolved:** Confirm caller survey — any tests use sampling mode?
