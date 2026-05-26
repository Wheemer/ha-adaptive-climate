# Low 09: bare except stringifies exception with possible IDs

**File:** `services/__init__.py:148-153, 311-318`

**Problem:** `except Exception as e` includes message with entity IDs / values.

**Fix:**
1. Privacy review: scrub sensitive fields before logging.
2. Replace with specific exception types where possible.

**Test:** Manual review.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
