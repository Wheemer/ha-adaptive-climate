# High 11: Auto-learning setback piggybacks on night transition signal

**File:** `managers/night_setback_manager.py:248-269`

**Problem:** Returns `(effective_target, True, info)` for auto-learning path even when user never configured night setback. Downstream (`_apply_night_setback_to_target`, learning grace) treats as regular transition → 60-min learning grace twice daily for users who never opted in. Also `info` missing `night_setback_end` → KeyError risk.

**Fix:**
1. Auto-learning path returns dedicated tuple/flag (e.g. `is_auto_learning=True` separate from `in_night_period`).
2. Climate entity branches on `is_auto_learning` to skip night-setback grace logic.
3. Add `night_setback_end` to `info` dict or guard downstream KeyError.
4. Cross-link with `auto_learning_setback` handling in climate.

**Test:** Unit: trigger auto-learning setback, assert no learning grace activated. Integration: user with no night setback config, assert no grace logged.

**Risk:** Med — touches semantic of return value.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Should auto-learning still emit its own learning-grace (smaller window) or none at all?
