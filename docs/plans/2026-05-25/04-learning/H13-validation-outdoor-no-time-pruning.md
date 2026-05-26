# High 13: Outdoor temp history count-pruned, not time-pruned

**File:** `adaptive/validation.py:294-296`

**Problem:** Last 30 raw readings; on-change sensors can fill window in minutes during weather transitions → seasonal-shift detection dormant.

**Fix:**
1. Store as list of `(ts, temp)` tuples.
2. Prune by max age (24h).
3. Optionally also cap count (50) as safety.

**Test:** Unit: feed 30 readings in 5 min → pruned to <30 after 24h boundary; `old_avg` vs `new_avg` spans real time.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
