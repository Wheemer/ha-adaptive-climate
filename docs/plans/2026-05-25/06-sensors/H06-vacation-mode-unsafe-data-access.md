# High 06: Vacation mode bypasses schema with raw data access

**File:** `services/__init__.py:218-219`

**Problem:** `call.data["enabled"]` raises KeyError if schema refactored. Currently safe but brittle.

**Fix:**
1. Use `call.data.get("enabled", False)`.
2. Add docstring noting schema dependency.

**Test:** Unit: call with missing `enabled`; assert default `False`.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
