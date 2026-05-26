# Low 32: Type-hint inconsistencies and missing annotations

**File:** `pid_controller/__init__.py:42`, `managers/ke_manager.py:50-61`, `managers/pid_tuning.py:42`

**Problem:** `_error = 0` (int) vs `error: float`; `callable | None` (builtin, not type); `gains_manager: Any` despite TYPE_CHECKING import.

**Fix:**
1. Init `_error = 0.0`.
2. Annotate all `__init__` params in PID class.
3. Replace `callable | None` with `Callable[..., Any] | None`.
4. Replace `Any` with `PIDGainsManager` (TYPE_CHECKING).
5. Run pyright strict.

**Test:** `pyright` clean for these files.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
