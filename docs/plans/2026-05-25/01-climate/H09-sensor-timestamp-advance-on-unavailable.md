# High 09: sensor timestamps advance even on UNAVAILABLE → derivative kick on next valid read

**File:** `custom_components/adaptive_climate/climate_handlers.py:35-37,233-243`

**Problem:** `_previous_temp_time = _cur_temp_time; _cur_temp_time = time.monotonic()` runs BEFORE `_async_update_temp`. Early-return on UNAVAILABLE/UNKNOWN leaves dt window advanced; next valid reading sees stretched dt with stale-vs-new temp → derivative kick.

**Fix:**
1. Move timestamp updates AFTER successful temp parse in `_async_update_temp`.
2. Or guard: only advance timestamps if state in `(STATE_UNAVAILABLE, STATE_UNKNOWN)` is False.

**Test:** Unit: feed sensor UNAVAILABLE then valid value → PID dt reflects only valid interval, no derivative spike.

**Risk:** Med — temp pipeline change touches PID derivative behavior.

**Depends on:** none.

**Blocks:** none.
