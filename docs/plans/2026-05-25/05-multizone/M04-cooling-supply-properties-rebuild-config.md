# Medium 04: Cooling supply props rebuild `auto_mode_config` per read

**File:** `coordinator.py:265-293`

**Problem:** Both properties build `auto_mode_config = self._config.get(...)` each access. Also `cooling_supply_temp` `or` chain swallows literal `0`.

**Fix:**
1. Cache `_auto_mode_config` in `__init__`.
2. Use `is not None` check for `cooling_supply_temp`.
3. Validate `cooling_supply_temp != 0` at config-flow (zero invalid anyway).

**Test:** Unit: assert config cached. Pass `cooling_supply_temp=0`, assert config validation rejects.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
