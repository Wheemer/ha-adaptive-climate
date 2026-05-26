# Medium 07: _schedule_learning_save uses inline hass.data lookup (anti-pattern)

**File:** `managers/cycle_metrics.py:319-347`

**Problem:** `self._hass.data.get(DOMAIN, {}).get("learning_store")` per cycle. CLAUDE.md mandates injected dependency / cached property.

**Fix:**
1. Define `LearningStoreProtocol` (async_save_zone signature).
2. Inject in `CycleMetricsRecorder.__init__`.
3. Replace inline lookup with `self._learning_store.async_save_zone(...)`.
4. Update factory/setup wiring.

**Test:** Unit test with mock LearningStoreProtocol — assert called on cycle finalization.

**Risk:** Low — DI refactor.

**Depends on:** none.

**Blocks:** A03 (cleanup theme).
