# Medium 06: zone_issues uncapped in state attrs

**File:** `sensors/health.py:64-74`

**Problem:** Full nested issues dict emitted on every state write; misbehaving system bloats recorder.

**Fix:**
1. Cap to top-N (e.g., 5) most-severe issues in attribute.
2. Expose full list via service call.
3. Add issue_count field.

**Test:** Unit: 20 issues; assert attr ≤5, count=20.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
