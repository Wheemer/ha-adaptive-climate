# Critical 03: Auto-apply counter mode-confused (cooling counts as heating)

**File:** `managers/pid_tuning.py:324, 328` + `adaptive/learning.py:281-284` + `adaptive/confidence.py:220`

**Problem:** `adaptive_learner._auto_apply_count += 1` always writes `_heating_auto_apply_count` via alias. Cooling auto-applies mis-counted; cooling stays at "first apply" gate; heating budget consumed silently.

**Fix:**
1. Replace `adaptive_learner._auto_apply_count += 1` in `pid_tuning.py:324, 328` with `adaptive_learner._confidence.increment_auto_apply_count(mode)`.
2. Remove or deprecate the mode-less `_auto_apply_count` alias at `learning.py:281-284`.
3. Audit all writers of `_auto_apply_count` / `_heating_auto_apply_count` / `_cooling_auto_apply_count` — funnel through tracker method.

**Test:** Unit: trigger cool auto-apply 2x → `get_auto_apply_count(COOL) == 2`, heating count unchanged. Integration: cooling re-enters "subsequent" gate after first apply.

**Risk:** Med — touches auto-apply hot path.

**Depends on:** none.

**Blocks:** none.
