# High 08: `_async_control_heating` time_func arg untyped (datetime from interval timer)

**File:** `custom_components/adaptive_climate/climate.py:783`, `climate_control.py:28`

**Problem:** `async_track_time_interval` passes datetime positionally; signature has `time_func: object = None`. Value unused but type wrong.

**Fix:**
1. Retype to `time_func: datetime | None = None`.
2. Add docstring: "passed by async_track_time_interval; unused".
3. Or remove parameter and wrap registration with lambda discarding the arg.

**Test:** Pyright clean.

**Risk:** Low.

**Depends on:** none.

**Blocks:** none.
