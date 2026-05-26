# Medium 10: Bare `datetime.fromisoformat` calls — three sites

**File:** `adaptive/learning.py:103-113`; `adaptive/learner_serialization.py:262-265`; `adaptive/preheat.py:381`

**Problem:** No try/except → corrupt/hand-edited ts crashes call chain.

**Fix:**
1. Add helper `safe_parse_iso(s) -> datetime | None` in `util.py` or local module.
2. Wrap each call; log WARN + return None on parse fail.
3. Callers handle None gracefully (skip / fallback).

**Test:** Unit: feed corrupt iso strings → no raise, returns None.

**Risk:** Low.

**Depends on:** none.

**Blocks:** H06 (combined with per-obs try/except).
