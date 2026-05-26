# High 08: `_last_session_avg_duty` accessed before init

**File:** `adaptive/heating_rate_learner.py:368-371, 254, 257`

**Problem:** `should_boost_ki` references attr only set in `end_session` when `session.cycle_duties` truthy. Discarded sessions never assign → `AttributeError`.

**Fix:**
1. Add `self._last_session_avg_duty: float | None = None` in `__init__`.
2. Guard `should_boost_ki`: `if self._last_session_avg_duty is None: return False`.

**Test:** Unit: fresh instance → `should_boost_ki()` returns False, no error.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
