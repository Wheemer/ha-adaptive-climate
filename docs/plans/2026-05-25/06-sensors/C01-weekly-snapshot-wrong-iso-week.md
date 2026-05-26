# Critical 01: Weekly snapshot tagged with wrong ISO week

**File:** `services/scheduled.py:191-194`

**Problem:** `isocalendar()` called on `end_date` (today) instead of report period. Sunday runs tag report covering prior 7 days with current week N, colliding with next run's lookup via `HistoryStore.get_previous_week()`.

**Fix:**
1. Derive `year, week_number = (end_date - timedelta(days=1)).isocalendar()[:2]` or use `start_date.isocalendar()`.
2. Add unit test: run snapshot on Sunday, assert week_number = prior week.
3. Verify `HistoryStore.get_previous_week()` queries match.

**Test:** Unit test mocking `dt_util.utcnow()` across Sun/Mon boundary; assert correct week tag.

**Risk:** Low. Pure date arithmetic.

**Depends on:** none.

**Blocks:** H04 (same file portability fix).
