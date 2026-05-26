# Critical 06: `format_version` int vs string mismatch

**File:** `adaptive/learner_serialization.py:189`

**Problem:** `_default_learner_state()` writes `"format_version": "v10"` (string); `learner_to_dict` writes int `10`; check at line 216 compares int. Default state round-trip would fail version check.

**Fix:**
1. Define module constant `CURRENT_FORMAT_VERSION: int = 10`.
2. Use everywhere (`_default_learner_state`, `learner_to_dict`, version check).
3. Add `int(stored_version)` coercion in the check for defensive compat.

**Test:** Unit: round-trip default state → version check passes; round-trip dict from `learner_to_dict` → same.

**Risk:** Low.

**Depends on:** none.

**Blocks:** C05.
