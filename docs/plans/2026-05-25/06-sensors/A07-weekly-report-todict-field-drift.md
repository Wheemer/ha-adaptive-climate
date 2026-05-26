# Architectural 07: WeeklyReport.to_dict drops fields

**File:** `analytics/reports.py:230-246`

**Problem:** Omits recovery_cycles, humidity_pauses, contact_pauses, comfort_score_prev, learning_status_prev. Silent data loss if to_dict used for serialization.

**Fix:**
1. Use `dataclasses.asdict(self)` or mirror all fields explicitly.
2. Add `__post_init__` test: assert to_dict round-trips.

**Test:** Unit: instance → to_dict → from_dict (if reconstructor exists); assert equal.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
