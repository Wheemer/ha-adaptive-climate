# Architectural 06: PWMController _last_accumulator_calc_time not persisted

**File:** `managers/pwm_controller.py`

**Problem:** `_duty_accumulator_seconds` persists via RestoreEntity, but `_last_accumulator_calc_time` resets to None. First post-restart tick baselines (no accumulation) — correct, but undocumented; monotonic time is process-relative.

**Fix:**
1. Add inline comment explaining "first tick post-restart baselines, no missed-duty accumulation".
2. Optionally persist wall-clock `last_calc_utc` and use it on restart to gracefully bridge gap (decay accumulator over downtime).

**Test:** Restart simulation — assert accumulator behavior matches documented intent.

**Risk:** Low (docs) / Med (if implementing bridge).

**Depends on:** H05 (related restart-safety theme).

**Blocks:** none.

**Unresolved:** Bridge gap with wall-clock or accept reset? Reset simpler and avoids stale-state risk.
