# Critical 1: PID uses wall-clock `time()` for dt

**File:** `pid_controller/__init__.py:5,514,532,537`

**Problem:** PID imports `from time import time`; NTP step / DST jump injects multi-hour `dt` into Ki, causing massive windup. CLAUDE.md mandates `time.monotonic()` for elapsed durations.

**Fix:**
1. Replace `from time import time` with `from time import monotonic`.
2. Update line 514 sampling-period gate to use `monotonic()`.
3. Update line 532 fallback and 537 sampling-period assignment to `monotonic()`.
4. Verify `ControlOutputManager` already passes monotonic-based `input_time`; remove dead sampling-period branch if unused.

**Test:** Unit: simulate `monotonic()` jump, assert integral unchanged. Integration: PID test suite passes.

**Risk:** Low. Mechanical swap, monotonic is the correct primitive.

**Depends on:** none.

**Blocks:** A03 (sampling-period bifurcation cleanup).
