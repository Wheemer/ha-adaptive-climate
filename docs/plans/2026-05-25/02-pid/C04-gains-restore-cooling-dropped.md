# Critical 4: `PIDGainsManager.restore_from_state` drops cooling gains

**File:** `managers/pid_gains_manager.py:212-242`

**Problem:** Only `mode_key="heating"` processed on restore. Cooling history persisted (line 405-411) but never re-synced to controller. Cooling-mode restarts run with init gains until manual reapply.

**Fix:**
1. Iterate both `heating` and `cooling` mode keys in `restore_from_state`.
2. Sync to PID controller based on current `hvac_mode`; store the other mode's gains for later switch.
3. Verify dedup (`_gains_match_last_entry`) prevents duplicate RESTORE snapshot.

**Test:** Unit: persist cooling gains, restart in COOL mode, assert controller has restored cooling gains.

**Risk:** Low. Symmetric extension of existing logic.

**Depends on:** none.

**Blocks:** none.
