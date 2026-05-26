# Critical 09: Undershoot cooldown bypassed on restart via historic scan

**File:** `adaptive/undershoot_detector.py:398-434` + `adaptive/learning.py:1690`

**Problem:** `_in_cooldown` mixes `time.monotonic()` (in-session) with wall-clock for cross-restart. After restart `last_adjustment_time` is None; `_perform_historic_scan` calls `should_adjust_ki` without `pid_history` → history-based check disabled → boost re-applied immediately after restart.

**Fix:**
1. Change `last_adjustment_time` to store wall-clock `dt_util.utcnow()` (datetime).
2. Persist as ISO string in `learner_to_dict` and restore in `restore_learner_from_dict` (datetime parse with try/except).
3. Cooldown check: `(dt_util.utcnow() - last_adjustment_time) < timedelta(...)`.
4. Always pass `pid_history` from `pid_gains_manager` to `should_adjust_ki` in `_perform_historic_scan`.

**Test:** Unit: simulate restart with recent `last_adjustment_time` → boost blocked. Historic scan path uses real history.

**Risk:** Med — touches cooldown invariant.

**Depends on:** C10 (related serialization fix).

**Blocks:** none.
