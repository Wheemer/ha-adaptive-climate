# Critical 10: `last_adjustment_time` monotonic float serialized as garbage

**File:** `adaptive/learner_serialization.py:90`

**Problem:** Writes `time.monotonic()` float into persistent storage; meaningless across restart (monotonic origin changes per boot); `restore_from_dict` doesn't read it back.

**Fix:**
1. Replace `last_adjustment_time` storage with ISO datetime string (per C09).
2. Add restore path; clamp to "not in future".
3. If old (float) payload encountered: ignore field, log INFO once.

**Test:** Unit: save with last_adjustment_time set → reload → datetime restored correctly; old float payload accepted without crash.

**Risk:** Low.

**Depends on:** none (paired with C09).

**Blocks:** C09.
