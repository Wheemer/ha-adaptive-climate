# Medium 19: `_input_time` / `_last_input_time` arithmetic without None narrowing

**File:** `pid_controller/__init__.py:118,119,469`

**Problem:** Pyright strict should flag `elapsed = _input_time - _dead_time_start` when either may be None. Runtime correct, type-unsafe.

**Fix:**
1. Add explicit annotations: `_input_time: float | None = None`.
2. At each arithmetic site, narrow with `if x is None: raise ValueError(...)` (per CLAUDE.md: never `assert`).
3. Run pyright on `pid_controller/__init__.py` to confirm clean.

**Test:** `pyright custom_components/adaptive_climate/pid_controller/` passes strict.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
