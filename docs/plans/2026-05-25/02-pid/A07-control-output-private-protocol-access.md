# Architectural 7: `ControlOutputManager` mixes public + private protocol attrs

**File:** `managers/control_output.py` (multiple)

**Problem:** Reads `_previous_temp_time`, `_current_temp`, `_ext_temp` alongside `current_temperature`. Inconsistent convention.

**Fix:**
1. Define convention: protocol attrs all public (no leading underscore).
2. Rename protocol fields: `previous_temp_time`, `current_temp`, `ext_temp`.
3. Update protocol + implementation + all readers.
4. Coordinate with broader Protocol audit (cross-cutting theme E).

**Test:** Pyright clean; tests pass.

**Risk:** Med. Wide rename.

**Depends on:** none.

**Blocks:** none. Coordinate with stream-wide Protocol cleanup.
