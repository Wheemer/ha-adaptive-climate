# Critical 07: Week boundary uses UTC ISO Monday, not local Sunday

**File:** `sensors/energy.py:447-476`

**Problem:** Docstring says "Sunday midnight reset" but code uses `dt_util.utcnow()` + ISO `isocalendar()` (week starts Monday). Negative-UTC users get Sunday-afternoon resets.

**Fix:**
1. Use `dt_util.now()` (local) and explicit weekday check (`.weekday() == 6` Sunday or `== 0` Monday — pick one).
2. Document chosen behavior in docstring.
3. Update boundary persistence to store local naive or UTC consistently.

**Test:** Unit: mock local time across Sun/Mon boundary in non-UTC zones (e.g., UTC-5, UTC+12); assert correct reset.

**Risk:** Med. Existing persisted boundary timestamps may mismatch new logic; add migration on restore.

**Depends on:** none.

**Blocks:** C08, M05 (meter reset detection in same file).
