# High 01: Flat preheat/humidity attrs violate documented schema

**File:** `state_attributes.py:104-108` (and `_add_preheat_attributes`, `_add_humidity_detection_attributes`)

**Problem:** Per CLAUDE.md, preheat/humidity belong under `debug.*` group. Code writes flat top-level (`preheat_active`, `humidity_detection_state`, etc.) unconditionally and ignores debug gate for humidity.

**Fix:**
1. Move preheat fields into `debug.preheat.*` dict; gate on `debug=True`.
2. Move humidity fields into `debug.humidity.*` and override entry; gate on `debug=True`.
3. Remove flat top-level emissions.
4. Update docs/tests accordingly.

**Test:** Unit: with debug off/on, assert schema matches CLAUDE.md.

**Risk:** Med. Users/automations reading flat attrs break.

**Depends on:** C05.

**Blocks:** H02 (humidity duplicate representation).
