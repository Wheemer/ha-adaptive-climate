# High 07: PID recommendations use fabricated baseline gains

**File:** `services/scheduled.py:482-484`

**Problem:** Defaults `current_kp=100.0, current_ki=0.01, current_kd=0.0` when state attrs missing. Feeds bogus baseline to `calculate_pid_adjustment`; user sees panic-inducing "Kp 1.5 vs current 100".

**Fix:**
1. Skip zone if any of kp/ki/kd unavailable.
2. Log warning with zone_id and missing fields.
3. Never substitute defaults.

**Test:** Unit: call with missing gains; assert zone skipped, warning logged.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
