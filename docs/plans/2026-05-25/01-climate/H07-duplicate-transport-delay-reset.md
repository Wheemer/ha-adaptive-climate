# High 07: duplicated transport-delay reset in turn_off vs HEATING_ENDED event

**File:** `custom_components/adaptive_climate/climate.py:1879-1881,1893`

**Problem:** `_async_heater_turn_off` resets `_transport_delay`; `_on_heating_ended_event` also resets. If event fires before turn-off, dead-time reset happens twice. Race-prone.

**Fix:**
1. Pick single owner: HEATING_ENDED event (more accurate signal).
2. Remove reset from `_async_heater_turn_off`.
3. Document who owns transport_delay lifecycle in comment.

**Test:** Unit: emit HEATING_ENDED after turn_off → no double-reset side effect. Integration: cycle with transport delay clears cleanly once.

**Risk:** Low.

**Depends on:** C02 (unit fix first).

**Blocks:** A06.
