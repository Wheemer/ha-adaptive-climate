# Medium 12: Persistence accepts v1-v5 without migration

**File:** `adaptive/persistence.py:71, 122`

**Problem:** Version check accepts 1-STORAGE_VERSION but loader stores as-is. Older shapes crash downstream.

**Fix:**
1. Add `_migrate_store(data, from_version)` dispatch.
2. Implement no-op or shape-adapter per version.
3. Reject (with WARN + fresh state) versions outside `[1, STORAGE_VERSION]`.

**Test:** Unit: load each historical version → produces v5 shape.

**Risk:** Med — affects user data.

**Depends on:** C05 (paired migration story).

**Blocks:** A03.
