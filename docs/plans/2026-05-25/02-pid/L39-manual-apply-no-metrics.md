# Low 39: `async_apply_adaptive_pid` does not pass metrics

**File:** `managers/pid_tuning.py:213-218`

**Problem:** Manual apply records no metrics in history snapshot; auto-apply does.

**Fix:**
1. Extract current metrics dict (overshoot, undershoot, settling_mae, drift) before set_gains.
2. Pass as `metrics=...` to `set_gains` call (matching auto-apply pattern at line 314-318).

**Test:** Unit: manual apply, assert history entry has metrics dict.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
