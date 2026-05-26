# Medium 08: `"stable"` returned from two semantically different paths

**File:** `adaptive/auto_apply.py:113-127`

**Problem:** Lines 125 and 127 both return `"stable"` but meanings differ ("degraded tuned" vs "honest stable"). Outside indistinguishable.

**Fix:**
1. Add new status `"tuned_pending"` for tier_2 confidence but insufficient recovery cycles.
2. Update `_compute_learning_status` callers and CLAUDE.md to recognize it (treat as ≈ stable for gating).
3. Optionally expose in status attribute for diagnostics.

**Test:** Unit: high confidence + low recovery cycles → `"tuned_pending"`; tier_1 met + tier_2 not → `"stable"`.

**Risk:** Low — additive enum value.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** UI / docs implications of new status value?
