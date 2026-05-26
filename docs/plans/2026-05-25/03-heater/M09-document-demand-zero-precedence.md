# Medium 09: Document demand-zero takes precedence over low-output timer

**File:** `managers/heater_controller.py:1027-1042`

**Problem:** Asymmetric "demand-zero cancels low-output timer" rule determines learning-cycle boundaries; not documented.

**Fix:**
1. Add docstring on `_low_output_timer` / `_demand_zero_timer` describing precedence.
2. Note the 0 → small → 0 dither sequence handling.
3. Add an inline `# DEMAND-ZERO PRIORITY:` comment.

**Test:** N/A (docs only).

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
