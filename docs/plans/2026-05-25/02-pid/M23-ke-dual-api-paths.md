# Medium 23: `KeManager` keeps both Protocol and callback paths

**File:** `managers/ke_manager.py:43-122,151-197`

**Problem:** Violates CLAUDE.md "managers receive Protocol". Doubles surface area, untestable dead branches.

**Fix:**
1. Audit all `KeManager` instantiation sites — confirm all pass `KeManagerState` protocol.
2. Delete callback constructor params and `if self._state is not None: ... else ...` branches.
3. Update tests to inject protocol mock only.

**Test:** All ke_manager tests pass; coverage of callback branches drops to zero (deleted).

**Risk:** Med. Breaking change for any out-of-tree caller (none in repo).

**Depends on:** none.

**Blocks:** A02.
