# Medium 14: display_name title() butchers IDs

**File:** `analytics/reports.py:43`

**Problem:** `bedroom_2nd_floor` → `Bedroom 2Nd Floor`.

**Fix:**
1. Prefer zone_name lookup from coordinator/config.
2. Fallback: smarter title-case (skip alphanumeric mid-token).

**Test:** Unit: known ugly IDs; assert sensible output.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
