# Low 16: Hardcoded English in reports

**File:** `analytics/reports.py:225`

**Problem:** `"All zones progressing normally"` not i18n'd.

**Fix:**
1. Document for future i18n.
2. Optional: extract to `_("...")` if HA translation framework adopted.

**Test:** N/A.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Should reports localize now or defer to i18n epic?
