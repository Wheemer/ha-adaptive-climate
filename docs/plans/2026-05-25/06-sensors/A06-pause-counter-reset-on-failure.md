# Architectural 06: Pause counters not reset if snapshot save fails

**File:** `services/scheduled.py:363-370`

**Problem:** `reset_pause_counters()` after snapshot save. If save raises, counters never reset → next week double-counts.

**Fix:**
1. Wrap save+reset in try/finally; reset always runs.
2. Or: reset BEFORE save; on save failure, snapshot is retried next run but counters already cleared (acceptable loss).

**Test:** Unit: mock save raise; assert reset called.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Reset-first vs reset-after-success — which loss is preferred?
