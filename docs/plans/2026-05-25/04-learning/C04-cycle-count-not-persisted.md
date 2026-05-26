# Critical 04: `_heating_cycle_count` / `_cooling_cycle_count` never serialized

**File:** `adaptive/confidence.py:56-57, 122-124` + `adaptive/learner_serialization.py`

**Problem:** Counts incremented but missing from `learner_to_dict`. After restart, `get_cycle_count(mode)==0` despite 50-entry history → `_compute_learning_status` returns "collecting" → auto-apply blocked until cycles re-accumulate.

**Fix:**
1. Preferred: change `ConfidenceTracker.get_cycle_count(mode)` to return `len(cycle_history[mode])` (drop the counter entirely).
2. If counter must remain: add `heating_cycle_count`, `cooling_cycle_count` to `learner_to_dict` and restore in `restore_learner_from_dict`.
3. Add backward-compat: if missing in payload, derive from `len(cycle_history)`.

**Test:** Unit: save w/ 50 cycles → restore → `get_cycle_count == 50`. Integration: restart preserves learning_status tier.

**Risk:** Low — additive.

**Depends on:** none.

**Blocks:** none.
