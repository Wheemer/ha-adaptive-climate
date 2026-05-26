# Low 14: `zone_id = slugify(name)` no de-duplication

**File:** `custom_components/adaptive_climate/climate_setup.py:208`

**Problem:** Two zones with names slugifying to same string silently collide.

**Fix:**
1. Check coordinator registry for existing zone_id.
2. On collision: raise ConfigEntryError with clear message, or append numeric suffix.

**Test:** Unit: two zones named "Living Room" and "living-room" → conflict raised.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
