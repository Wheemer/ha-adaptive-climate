# High 04: sampling_period=0 default silently triggers DEFAULT_CONTROL_INTERVAL fallback

**File:** `custom_components/adaptive_climate/climate.py:782-787,443`

**Problem:** `_sampling_period` defaults `00:00:00` → 0. Fallback `_sampling_period > 0` always falls to 60s default. Zero sampling_period also passed to `PID(sampling_period=...)` — may break integral math.

**Fix:**
1. Set platform schema default for `sampling_period` to non-zero (60s) or document and validate.
2. Reject `sampling_period=0` at schema level.
3. Verify PIDController handles 0 sampling_period (guard with max(1, sp)).
4. Add comment clarifying control_interval > sampling_period > 60s precedence.

**Test:** Unit: instantiate PID with sampling_period=0 → no div-by-zero; entity with no config uses 60s.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
