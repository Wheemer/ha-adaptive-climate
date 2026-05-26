# Arch 07: Coordinator returns mutable live dict from `_async_update_data`

**File:** `coordinator.py` (`_async_update_data`)

**Problem:** Returns `{"zones": self._zones, ...}` — live mutable dict. Consumer mutation corrupts coordinator state.

**Fix:**
1. Wrap in `MappingProxyType(self._zones)` for read-only view.
2. Or return shallow copy.
3. Document immutability in docstring.

**Test:** Unit: consumer attempts mutation, assert TypeError or copy semantics.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
