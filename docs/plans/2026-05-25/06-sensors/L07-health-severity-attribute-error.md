# Low 07: issue.severity.value assumes enum

**File:** `sensors/health.py:67`

**Problem:** If legacy code returns string severity, `.value` raises AttributeError.

**Fix:**
1. Type-narrow: `getattr(issue.severity, "value", issue.severity)`.

**Test:** Unit: pass string severity; assert no exception.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
