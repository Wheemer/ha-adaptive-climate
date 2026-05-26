# Medium 05: `check_rate_based_undershoot` never called

**File:** `adaptive/undershoot_detector.py:478-525`

**Problem:** Third mode advertised in docstring but unwired.

**Fix:**
1. Decide: wire into `check_undershoot_adjustment` (alongside realtime + cycle) OR delete method + update docstring.
2. If wired: add to `learning.py:check_undershoot_adjustment` call chain.

**Test:** Unit: rate-based scenario triggers boost; non-trigger scenarios don't.

**Risk:** Low (delete) or Med (wire — new active path).

**Depends on:** none.

**Blocks:** none.

**Unresolved:** Keep or delete? Defer to hvac-expert / product decision.
