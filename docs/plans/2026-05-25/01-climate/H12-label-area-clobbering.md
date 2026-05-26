# High 12: `_async_assign_label` and `_async_assign_area` clobber user customizations on restart

**File:** `custom_components/adaptive_climate/climate.py:586-606`

**Problem:** `entity_registry.async_update_entity(labels={label.label_id})` replaces label set; user-added labels lost every HA restart. Area similarly clobbered.

**Fix:**
1. Labels: read existing `labels` from entity registry entry, union with integration label, write union.
2. Area: only assign if `entry.area_id is None`. Or only on first registration (track via stored flag).

**Test:** Unit: pre-existing labels preserved after `_async_assign_label`. Manual: add label/area in UI, restart, verify retained.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
