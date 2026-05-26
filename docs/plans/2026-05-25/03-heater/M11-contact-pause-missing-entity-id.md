# Medium 11: _on_contact_pause ignores event.entity_id

**File:** `managers/cycle_tracker.py:443-454`

**Problem:** Hardcoded reason string drops entity_id from event payload.

**Fix:**
1. Read `event.entity_id` from payload.
2. Include in reason string: `f"contact sensor pause ({entity_id} opened)"`.

**Test:** Unit test multi-sensor pause — assert reason string includes triggering entity.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
