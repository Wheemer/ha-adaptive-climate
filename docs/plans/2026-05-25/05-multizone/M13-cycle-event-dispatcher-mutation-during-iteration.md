# Medium 13: `CycleEventDispatcher.emit` mutation-during-iteration risk

**File:** `managers/events.py:189-230`

**Problem:** Listener calling `subscribe`/`unsubscribe` during dispatch → `RuntimeError: list changed size during iteration`.

**Fix:**
1. Iterate over `self._listeners[event_type].copy()` (or tuple).
2. Add unit test with one-shot listener.

**Test:** Unit: listener unsubscribes itself during emit, assert no error, subsequent emits clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
