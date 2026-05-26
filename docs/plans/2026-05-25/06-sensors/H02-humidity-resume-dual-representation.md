# High 02: humidity_resume_in (int seconds) vs override resume_at (ISO)

**File:** `state_attributes.py:443-457`

**Problem:** Two representations of the same data (seconds-int vs ISO8601) emitted simultaneously. Bug-prone.

**Fix:**
1. Drop `humidity_resume_in` flat attr.
2. Keep `resume_at` ISO8601 inside `status.overrides[].humidity`.
3. If duration needed, compute client-side from `resume_at`.

**Test:** Unit: assert only one representation present.

**Risk:** Low.

**Depends on:** H01.

**Blocks:** none.
