# Architectural 08: Unify wall-clock vs monotonic policy

**File:** multiple — undershoot cooldown, serialization, etc.

**Problem:** Mix of `time.monotonic()` (persisted as garbage) and `dt_util.utcnow()`. Cross-restart bridging fails.

**Fix:**
1. Policy: `time.monotonic()` only for in-process elapsed durations never persisted; `dt_util.utcnow()` for anything crossing persistence/restart.
2. Audit + refactor each holder.
3. Add lint rule: persisted dict values cannot derive from `monotonic()`.

**Test:** Unit per holder; cross-restart correctness preserved.

**Risk:** Med.

**Depends on:** C09, C10.

**Blocks:** A04.
