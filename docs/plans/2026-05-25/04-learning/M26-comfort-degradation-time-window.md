# Medium 26: `deque(maxlen=288)` can hold multi-day data

**File:** `managers/comfort_degradation.py:30`

**Problem:** 288 samples assumed 5-min spacing; HA on-change can take days for 288.

**Fix:**
1. Store `(ts, score)` tuples.
2. Prune samples older than 24h on insert.
3. Keep maxlen as safety cap.

**Test:** Unit: feed sparse samples spanning 48h → rolling avg only uses last 24h.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
