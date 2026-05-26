# Medium 18: `_update_heater`/`_update_cooler` cancel-turnoff trace verification

**File:** `central_controller.py:113-153`

**Problem:** Reviewer self-downgrades but flags re-verification of demand-on-all-switches-on edge — `_cancel_heater_turnoff_unlocked` placement around line 122 needs traced confirmation.

**Fix:**
1. Trace demand-on/all-on path manually.
2. Add unit test: demand on → turnoff scheduled → demand returns → all switches still on → assert turnoff cancelled.
3. If race confirmed, move cancel above the early-return check.

**Test:** Unit: as above; assert turnoff cancelled even when no startup needed.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
