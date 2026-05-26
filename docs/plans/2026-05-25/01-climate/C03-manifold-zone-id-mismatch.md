# Critical 03: manifold lookup uses slug vs entity_id inconsistently

**File:** `climate_control.py:343`, `climate.py:1855`, `__init__.py:191`

**Problem:** `climate_control.py:343` passes `self._zone_id` (slug) to `coordinator.get_transport_delay_for_zone`; manifold registry keyed by `entity_id` (`cv.entity_id` in schema). Lookup returns None → 0 transport delay. `climate.py:1855` correctly uses `self.entity_id`.

**Fix:**
1. Pick canonical ID: `entity_id` (already in schema).
2. Update `climate_control.py:343` to use `self.entity_id`.
3. Add type alias `ZoneEntityId = str` and annotate registry signatures.
4. Add assertion in `ManifoldRegistry.get_manifold_for_zone` that input starts with `climate.`.

**Test:** Unit: `coordinator.get_transport_delay_for_zone(entity_id)` returns configured delay for manifold zone. Regression: same delay returned via both call sites.

**Risk:** Low — single-line fix, well-bounded.

**Depends on:** none.

**Blocks:** C02.
