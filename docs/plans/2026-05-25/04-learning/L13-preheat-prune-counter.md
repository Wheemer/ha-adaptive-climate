# Low 13: Preheat counter-based expiration non-deterministic

**File:** `adaptive/preheat.py:69`

**Problem:** "Every 10 calls" prune; can be slow with many bins.

**Fix:**
1. Replace counter with `last_prune_at: datetime`.
2. Prune if `now - last_prune_at > 1 day`.

**Test:** Unit: 100 adds in 1h → no prune; after 25h → prunes.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
