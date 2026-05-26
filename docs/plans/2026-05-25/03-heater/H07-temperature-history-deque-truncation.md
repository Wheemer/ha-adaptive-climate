# High 07: deque(maxlen=2000) silently truncates long settling windows

**File:** `managers/cycle_tracker.py:121`

**Problem:** At sub-30s sampling + SETTLING_TIMEOUT_MAX=240min → 2880 samples → oldest dropped. `temperature_history[0]` no longer cycle start; corrupts `inter_cycle_drift`/`settling_mae`.

**Fix:**
1. Capture `_cycle_start_temp` once at `_on_cycle_started` (timestamp + value).
2. Use captured value in all metrics instead of `temperature_history[0]`.
3. Optionally raise maxlen to handle worst-case (e.g., 5000).

**Test:** Unit test feed >2000 samples then finalize — assert metrics use captured start, not truncated head.

**Risk:** Low — additive capture.

**Depends on:** none.

**Blocks:** none.
