# Architectural 07: `asyncio.Lock` only used in one method; invites Heisenbugs

**File:** `custom_components/adaptive_climate/climate.py` (`_temp_lock`)

**Problem:** HA is single-threaded async; lock only matters for cooperative re-entry across awaits. Currently only `_async_control_heating` takes it. Half-measure.

**Fix:**
1. Decision: drop lock and document invariants OR apply on all methods that mutate control state.
2. Recommend: apply broadly to all `async_set_*` mode/temp/preset mutations (resolves C01 et al).
3. Document lock-protected methods with `# noqa: lock-required` markers or decorator.

**Test:** Concurrent stress test: rapid mode/temp/preset changes during control loop ticks → consistent final state.

**Risk:** Med.

**Depends on:** C01.

**Blocks:** none.
