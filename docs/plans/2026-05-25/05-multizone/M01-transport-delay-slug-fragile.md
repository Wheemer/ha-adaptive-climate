# Medium 01: `get_transport_delay_for_zone` uses fragile slug→entity reconstruction

**File:** `coordinator.py:147-160`

**Problem:** `f"climate.{zone_slug}"` breaks if user renames climate entity → transport delay silently returns 0.

**Fix:**
1. Store `climate_entity_id` in `zone_data` at registration.
2. Replace reconstruction with direct lookup.

**Test:** Unit: register zone with non-default entity_id, assert transport delay returned.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
