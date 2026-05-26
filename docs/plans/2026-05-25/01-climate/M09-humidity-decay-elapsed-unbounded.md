# Medium 09: humidity decay `elapsed` unbounded → integral collapses

**File:** `custom_components/adaptive_climate/climate_control.py:91-93`

**Problem:** First call after pause begins with unset `_last_control_time` → elapsed = HA uptime → `0.9^(huge)` ≈ 0, integral wiped.

**Fix:**
1. Initialize `_last_control_time = time.monotonic()` on first use.
2. Clamp `elapsed = min(elapsed, 600)` as safety.
3. Document expected range.

**Test:** Unit: first decay call with cold-start `_last_control_time` does not wipe integral.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
