# Medium 17: `clear_samples` does not reset all transient state

**File:** `pid_controller/__init__.py:393-400`

**Problem:** Residual `_external`, `_feedforward`, `_proportional`, `_derivative`, `_input_diff`, `_dext` from prior calc remain. `_proportional` not recomputed when `_last_input is None` on first calc.

**Fix:**
1. Reset `_proportional`, `_derivative`, `_input_diff`, `_dext`, `_external`, `_feedforward` to 0.0 in `clear_samples`.
2. Verify no logging code depends on these for last-known-good.

**Test:** Unit: OFF→AUTO, assert all transient fields zeroed before first calc.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
