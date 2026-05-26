# Low 25: `schedule_zone_save` lambda captures `self._data` by ref

**File:** `adaptive/persistence.py:194-213`

**Problem:** If `self._data` replaced before delayed save, new data saved. Probably correct, undocumented.

**Fix:**
1. Add code comment explaining intentional late binding.
2. Or snapshot: `data_copy = dict(self._data); lambda: data_copy`.

**Test:** None (documentation only) or unit test for replace-before-save semantics.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Late-binding intentional or accidental?
