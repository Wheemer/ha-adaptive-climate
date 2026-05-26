# High 03: pid_history flat attr risks recorder bloat

**File:** `state_attributes.py:65-75`

**Problem:** `pid_history` emitted flat per state write. ~50 entries × 6 fields → >2KB per state change to SQLite recorder.

**Fix:**
1. Verify `gains_manager.get_history()` enforces hard cap (e.g., last 100).
2. If not, add cap in PIDGainsManager.
3. Consider moving full history out of state attrs entirely (separate service or attribute exclusion via recorder filter).

**Test:** Unit: push 200 entries, assert get_history returns ≤cap. Integration: verify recorder size impact.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
