# High 13: Private attr access to _learning_grace_end

**File:** `managers/state_attributes.py:760-761`

**Problem:** `getattr(manager, "_learning_grace_end", None)` couples to NightSetbackManager internals. Rename silently returns None.

**Fix:**
1. Add public property `learning_grace_end` on NightSetbackManager.
2. Update state_attributes to use property.
3. Add Protocol method if needed.

**Test:** Unit: rename internal field, assert property still works.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
