# Low 27: Inline pluralization ugly

**File:** `managers/comfort_degradation.py:67-70`

**Problem:** `"pause{'s' if n != 1 else ''}"` inline.

**Fix:**
1. Add tiny util `pluralize(n, word, plural=None)` in shared utils.
2. Use everywhere.

**Test:** Unit on util.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
