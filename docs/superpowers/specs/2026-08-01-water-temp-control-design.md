# Water Temperature Control (Dew-Point Cooling + Startup Ramps)

**Date:** 2026-08-01
**Status:** Approved

## Purpose

Drive the heat pump's supply water temperature setpoints from Adaptive Climate:

- **Cooling:** compute the coldest condensation-safe water temperature from indoor dew point and push it to the heat pump's cooling-supply number entity.
- **Heating:** push a configured heating-supply target to a separate number entity.
- **Both:** when a mode resumes after a long idle period (e.g. seasonal switch), ramp the water temperature toward its target over days instead of stepping instantly.

The computed values are consumed by an **external system** (heat pump / mixing valve) via `number.set_value` service calls. They are not used internally by Adaptive Climate (see Future Work).

## Configuration (domain-level)

```yaml
adaptive_climate:
  water_temp_control:
    idle_days: 7                # ramp (re)starts when a mode resumes after >= this many days inactive
    cooling:
      target_entity: number.heatpump_cool_supply   # required
      floor: 18.0               # min water temp, degC
      margin: 2.0               # degC above dew point
      fallback_humidity: 60     # % RH for zones without humidity_sensor
      ramp_start: 22.0          # degC, ramp starting point
      ramp_rate: 1.0            # degC/day downward
    heating:
      target_entity: number.heatpump_heat_supply   # required
      target: 35.0              # degC; defaults to domain supply_temperature when omitted
      ramp_start: 25.0          # degC, ramp starting point
      ramp_rate: 2.0            # degC/day upward
```

`cooling:` and `heating:` blocks are each optional; configuring neither makes the whole feature inert. `heating.target` falls back to the existing domain `supply_temperature`; if neither is set, the heating block is invalid (voluptuous error).

## Behavior

### Cooling (active when >= 1 zone is in COOL mode)

1. For each COOL-mode zone: dew point = Magnus formula over (zone current temp, zone humidity). Humidity comes from the zone's `humidity_sensor` state; if the zone has no sensor or the sensor is unavailable, use `fallback_humidity`. Zones without a current temperature are skipped.
2. `dew_target = max(max(zone dew points) + margin, floor)`
3. During a ramp: `effective = max(dew_target, ramp_start - ramp_rate * days_since_ramp_start)`
4. Round to 0.5 degC steps; write to `cooling.target_entity` only when the rounded value differs from the last written value.

### Heating (active when >= 1 zone is in HEAT mode)

1. `heat_target = heating.target`
2. During a ramp: `effective = min(heat_target, ramp_start + ramp_rate * days_since_ramp_start)`
3. Same 0.5 degC rounding and write-on-change to `heating.target_entity`.

### Startup ramps

- A mode's ramp starts when that mode becomes active after being inactive for >= `idle_days`. "Active" = at least one zone in that HVAC mode.
- Heating and cooling track idle/ramp state independently.
- Brief shoulder-season HEAT/COOL flips (< `idle_days` idle) do NOT restart a ramp; a ramp already in progress continues from its own start time.
- A ramp ends when it reaches the target (cooling: ramp value <= dew_target; heating: ramp value >= heat_target). The dew_target moves with humidity; the ramp bound simply stops being the binding constraint.
- Last-active timestamp per mode and ramp start time persist via HA Store so restarts do not reset multi-day ramps.
- First run (no persisted state): treat the mode as long-idle, i.e. start with a ramp. This is the conservative choice for both directions.

### Actuation

- `number.set_value` via `hass.services.async_call`; service errors are logged and retried on the next cycle.
- No writes while a mode is inactive; the last written value is left as-is (the heat pump ignores the setpoint when that mode is off).
- Recompute every 5 minutes via `async_track_time_interval` (matches the sensor platform's polling pattern). Rounding makes writes rare (a handful/day).

## Architecture

| Piece | Location | Notes |
|-------|----------|-------|
| `dew_point(temp_c, rh_pct)` | `adaptive/dew_point.py` | Pure function, Magnus-Tetens (b=17.62, c=243.12) |
| `WaterTempController` | `managers/water_temp_control.py` | Pure-logic compute + service-call actuation; `*Controller` per naming convention (actuates external hardware) |
| Config schema | `__init__.py` `CONFIG_SCHEMA` | New `WATER_TEMP_CONTROL_SCHEMA` block |
| Wiring | `coordinator.py` | Coordinator constructs/owns the controller (same pattern as `AutoModeSwitchingManager`), feeds it zone registry data (mode, temp, humidity_sensor entity id) |
| Persistence | HA Store (`async_save_zone` store or a small dedicated Store key) | last_active per mode + ramp_started per mode |

Zone humidity sensor entity ids must be visible to the coordinator: include `humidity_sensor` in the zone registration data (`register_zone`). The controller reads sensor states from `hass.states` at compute time; no listeners on humidity sensors.

## Error Handling

- Unavailable/non-numeric humidity sensor state -> fallback_humidity for that zone.
- No COOL zones with a valid temp -> no cooling write that cycle.
- Target entity missing/unavailable -> log warning (rate-limited), retry next cycle.
- Value clamped to the target number entity's own min/max attributes when present, to avoid ServiceValidationError.

## Testing

`tests/test_water_temp_control.py` (+ `tests/test_dew_point.py`):

- Dew point function vs known psychrometric values (e.g. 25 degC / 60% -> ~16.7 degC).
- Worst-zone selection; fallback humidity for missing/unavailable sensors; zones without temp skipped.
- Floor, margin, 0.5 rounding; write-on-change (no duplicate service calls).
- Inactive mode -> no writes.
- Ramp: starts only after idle >= idle_days; direction per mode; converges and hands over to dew/static target; shoulder-season flip does not restart; state survives restore.
- Heating target fallback to `supply_temperature`; schema error when neither set.

## Future Work (explicitly out of scope)

- Feed the computed cooling water temp into the existing `min_cooling_target` setpoint clamp (coordinator.py) so zone setpoints track the achievable water temp; today that clamp uses the static `cooling_supply_temp` config.
- Outdoor-compensated heat curve for the heating target (weather-dependent supply temperature).
