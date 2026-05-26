# Medium 06: `coordinator.py` exceeds 800-line limit; extract ModeSync

**File:** `coordinator.py:699-948`

**Problem:** File at 948 lines (CLAUDE.md max 800). `ModeSync` bolted onto end. `central_controller.py` at 656 lines, approaching limit.

**Fix:**
1. Extract `ModeSync` → `coordinator/mode_sync.py` (or `managers/mode_sync.py`).
2. Update imports.
3. Defer `central_controller` refactor to A04 (DeviceController dedup).

**Test:** Existing test suite passes. `wc -l coordinator.py < 800`.

**Risk:** Low — pure move.

**Depends on:** none.

**Blocks:** A05.
