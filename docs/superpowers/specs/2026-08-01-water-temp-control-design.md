# Water Temperature Control (Dew-Point Cooling + Startup Ramps)

**Date:** 2026-08-01
**Status:** Approved (amended after HVAC + architecture review)

## Purpose

Drive the heat pump's supply water temperature setpoints from Adaptive Climate:

- **Cooling:** compute the coldest condensation-safe water temperature from indoor dew point and push it to the heat pump's cooling-supply number entity.
- **Heating:** push a configured heating-supply target to a separate number entity.
- **Both:** when a mode resumes after a long idle period (e.g. seasonal switch), ramp the water temperature toward its target over days instead of stepping instantly.

Values are consumed by an **external system** (heat pump / mixing valve) via `number.set_value` / `input_number.set_value`. The one internal consumer is the existing `min_cooling_target` setpoint clamp (see Cooling Clamp Unification).

## Configuration

Domain-level:

```yaml
adaptive_climate:
  water_temp_control:
    idle_days: 7                    # ramp (re)starts when a mode resumes after >= this many days inactive
    min_write_interval: 1800        # s between unsafe-direction writes (see Write Policy)
    condensation_sensor: binary_sensor.manifold_condensation   # optional interlock
    cooling:
      target_entity: number.heatpump_cool_supply   # required; number or input_number
      min_supply_temp: 18.0         # degC lower bound on water temp
      dew_point_margin: 2.0         # degC above dew point
      fallback_humidity: 65         # % RH when a zone has no usable reading
      ramp_start: 22.0              # degC
      ramp_rate: 1.0                # degC/day downward
      extra_sensors:                # optional non-zone locations (manifold cupboard, basement)
        - humidity: sensor.manifold_rh
          temperature: sensor.manifold_temp
    heating:
      target_entity: number.heatpump_heat_supply   # required; must differ from cooling target_entity
      target: 35.0                  # degC, Range(20, 45); defaults to domain supply_temperature
      ramp_start: 25.0              # degC
      ramp_rate: 2.0                # degC/day upward
```

Entity-level (climate platform): `exclude_from_dew_point: true` — omit this zone's humidity from the dew point scan (bathrooms, utility rooms).

Schema notes:
- `cooling:` / `heating:` blocks each optional; neither configured = feature inert.
- Naming avoids collision with existing `cooling_supply_margin` (different referent): new keys are `dew_point_margin` and `min_supply_temp`.
- `heating.target` falls back to domain `supply_temperature`. Neither set -> invalid; requires a domain-level `vol.All(schema, validator)` wrapper since the sibling key is outside `WATER_TEMP_CONTROL_SCHEMA`.
- Validate `cooling.target_entity != heating.target_entity`.
- Docs must warn: (a) the heating half overrides a heat pump's own weather-compensation curve — only configure it if the pump runs a fixed setpoint; (b) `supply_temperature` also feeds physics-based PID init, changing it changes both; (c) insulated supply pipework/manifold is a prerequisite for radiant cooling near dew point.

## Dew Point Computation (cooling)

Per included source, dew point via Magnus-Tetens (b=17.62, c=243.12) in a pure helper `helpers/dew_point.py`; `ValueError` on RH outside (0, 100] (no `assert`, per project rules).

**Sources scanned** (worst = max dew point wins):
- Every COOL-mode zone with a `humidity_sensor`, except zones with `exclude_from_dew_point: true` and zones whose `HumidityDetector` is in PAUSED/STABILIZING (a shower in progress is local + transient; the detector already knows).
- Each configured `extra_sensors` pair (always included, mode-independent placement like manifold cupboards).

**Temperature pairing** — RH is only meaningful with co-located temp; pairing the humidity reading with a differently-placed zone sensor can eat the whole margin. Resolution order per zone:
1. A temperature entity on the same device as the humidity sensor (entity/device registry lookup).
2. The zone's climate `current_temperature` attribute (log once at INFO; record source in debug attributes).

**Smoothing:** per-source 20-min EMA of RH, not instantaneous state — prevents one shower or a door swing from locking out house-wide cooling for hours of slab lag.

**Plausibility + staleness guards:**
- RH outside [15, 100] or temp outside [5, 40] degC -> implausible; use `fallback_humidity` for that source, WARNING (rate-limited).
- `state.last_updated` older than 60 min -> RH = `max(last_ema, fallback_humidity)` (a known-humid zone isn't optimistically forgotten).
- If **no** source has a real (plausible, fresh) humidity reading, the system is blind: effective supply is floored at `max(min_supply_temp, 20.0)` and a WARNING is logged.

Then: `dew_target = max(max(dew_points) + dew_point_margin, min_supply_temp)`.

## Targets and Ramps

- **Cooling active** (>= 1 zone in COOL): `effective = max(dew_target, ramp_start - ramp_rate * days_since_ramp_start)` while ramping, else `dew_target`.
- **Heating active** (>= 1 zone in HEAT): `effective = min(target, ramp_start + ramp_rate * days_since_ramp_start)` while ramping, else `target`.
- "Zone in mode X" = climate entity state (`get_zones_in_mode`, new coordinator helper reading `hass.states`) — NOT `get_active_zones()`, which filters on live demand and would drop satisfied zones. Entity state is also valid immediately after restart, unlike `_demand_states[zone]["mode"]`.
- Zone current temps likewise come from each zone's climate entity `current_temperature` attribute (`coordinator.update_zone_temp` has no production callers; the registry's temp map is empty in production).

**Ramp lifecycle:**
- A mode's ramp starts when that mode becomes active after >= `idle_days` inactive. Heating and cooling track idle/ramp state independently. Shoulder-season HEAT/COOL flips (< idle_days) never restart a ramp; an in-progress ramp continues from its own start time.
- **Heating ramp seeding:** `ramp_start_effective = max(configured ramp_start, current value of target_entity)` — a system already running hot (e.g. mid-winter first install) is never yanked down to 25 degC (backup-heater trap). Cooling always uses the configured `ramp_start` (seeding from the entity would start too cold on a warm slab).
- A ramp ends when its bound stops binding (cooling: ramp value <= dew_target; heating: >= target).
- First run (no persisted state): treat as long-idle -> ramp, conservative in both directions.
- Elapsed time via `dt_util.utcnow()` (never `time.monotonic()` — resets on restart). Clamp `days_since_ramp_start` to >= 0 and guard `now < ramp_started` on restore (clock corrections).

## Write Policy

- Round to the target entity's `step` attribute (fallback 0.5), **always toward the safe side**: cooling rounds up, heating rounds down. Nearest-rounding would silently spend safety margin.
- Clamp to the target entity's own min/max attributes; compare the **post-clamp, post-round** value against the last written value (comparing pre-clamp values re-issues identical calls forever when out of range).
- **Asymmetric throttling:** safe-direction changes (cooling: up, heating: down) write immediately on change. Unsafe-direction changes require the rounded change to persist for `min_write_interval` (default 1800 s) — prevents RH-noise dither and heat pump setpoint hunting.
- Service calls follow the `HeaterServiceCaller` shape (`get_number_entity_domain` resolves `number` vs `input_number`; ServiceNotFound/HomeAssistantError handling); failures logged (rate-limited) and retried next cycle.
- Compute once at `EVENT_HOMEASSISTANT_STARTED` (after a short startup delay so zones have registered and persisted state is restored), then every 5 min via `async_track_time_interval`. Callback body wrapped in try/except so one bad cycle can't kill the timer.
- **Mode deactivation:** park the entity at that mode's `ramp_start` value (one final write) rather than leaving the most aggressive value latched for the next season.

## Interlocks (cooling)

Immediately (bypassing `min_write_interval`) write the interlock park value — `max(ramp_start, current dew target)`, so an interlock can never LOWER the supply temperature — and hold while:
- `condensation_sensor` is ON (a strapped-on pipe sensor is a measurement; computed dew point is an inference), or
- any COOL zone reports an `open_window` or `contact_open` override (humid night air onto a cold slab is the top condensation event).

Resume normal computation 30 min after the condition clears.

## Learning Protection

Water-temp changes move the plant gain under the adaptive learner (zone gain ~ T_room - T_water); a multi-day ramp looks exactly like the `UndershootDetector` failure signature and would trigger Ki boosts + confidence loss that take weeks to unwind.

- Coordinator exposes `water_temp_learning_gate(mode) -> bool`: true while a ramp is active for that mode, and for one settling window after any write that changed the value >= 1.0 degC.
- While true, affected zones suppress cycle recording and undershoot detection, surfaced as the existing `learning_grace`-style override.

## Cooling Clamp Unification (in scope, not future work)

Today `min_cooling_target = cooling_supply_temp + cooling_supply_margin` (static) clamps zone setpoints (`climate.py:1006-1018`). With a dynamic supply temp, the static clamp lets zones chase setpoints the water can't deliver -> integral windup + spurious undershoot Ki boosts, and the `cooling_supply_clamp` status override displays a wrong value.

- When `water_temp_control.cooling` is configured, `coordinator.min_cooling_target` reads the controller's current effective supply temp (+ `cooling_supply_margin`), falling back to the static value when the controller hasn't computed yet.
- If the static `cooling_supply_temp` is also configured and differs from `min_supply_temp`, log a setup warning naming both.

## Architecture

| Piece | Location | Notes |
|-------|----------|-------|
| `dew_point(temp_c, rh_pct)` | `helpers/dew_point.py` | Pure function (stateless helper; `adaptive/` is learning/physics) |
| `WaterTempController` | `managers/water_temp_controller.py` | Matches `heater_controller.py` naming; `*Controller` = actuates external hardware |
| Config schema | `__init__.py` | `WATER_TEMP_CONTROL_SCHEMA` above `CONFIG_SCHEMA` + domain-level `vol.All` validator; mirror into the no-HA stub branch |
| Wiring | `coordinator.py` | Constructed in `coordinator.__init__` from `self._config.get(...)` (NOT `hass.data` — `supply_temperature` lands there only after the coordinator exists). Footprint ~15 lines (file is over the 800-line ceiling). Timer unsub cancelled in `async_cleanup()` |
| Zone data | `climate_setup.py` | Add `humidity_sensor` + `exclude_from_dew_point` to `register_zone` zone_data (config already read there) |
| Persistence | `adaptive/persistence.py` | Mirror `manifold_state`: top-level `water_temp_state` key in the learning store (`async_load/save_water_temp_state`), saved on stop + unload. Additive — no STORAGE_VERSION bump. Persist ISO timestamps: last_active per mode, ramp_started per mode, last_written per entity. Gate compute on a `_restored` flag |
| Diagnostics | `sensor.py` | One system-wide sensor: state = current effective supply temp; attributes: mode, dew_point, binding_constraint (dew_point / min_supply / ramp / target / interlock / blind), ramp_active, days_remaining, worst_source |

## Testing

`tests/test_dew_point.py`:
- Reference points: 25/60% -> 16.69; 20/50% -> 9.3; 30/80% -> 26.2. ValueError on RH <= 0, > 100.

`tests/test_water_temp_controller.py`:
- Worst-source selection incl. extra_sensors; excluded zones (flag, HumidityDetector paused); temp pairing resolution order.
- Plausibility (RH 0/1/101, temp 3/45), staleness (max(last_ema, fallback)), blind mode floors at 20.
- min_supply_temp, dew_point_margin, safe-direction rounding to entity step; post-clamp write comparison; no dither at a boundary under ±1% RH noise; unsafe-direction dwell honored, safe-direction bypasses it.
- Inactive mode -> no writes; deactivation parks at ramp_start.
- Ramps: idle-days trigger, direction per mode, heating seed from entity value, shoulder-flip no-restart, first-run ramp, persisted future timestamp clamps to 0, restore across restart.
- Heating target fallback to supply_temperature; schema errors (no target anywhere; same target_entity twice).
- Interlocks: condensation sensor / open-window force park immediately; 30-min stabilization on clear.
- Learning gate true during ramp and after >= 1.0 degC write; min_cooling_target follows dynamic value with static fallback.

Update `CLAUDE.md` (architecture + tests lists) and the GitHub wiki alongside implementation.

## Reviewer Defaults Kept As-Chosen (user decision)

- `dew_point_margin: 2.0` — HVAC review recommends 3.0 (combined RH+temp sensor uncertainty is realistically 1.3-1.8 degC). Kept at the user-approved 2.0; configurable.
- `cooling.ramp_rate: 1.0` degC/day — review suggests 1.5-2.0 (slab tau is hours, not days; dew-point logic already handles the humidity-pulldown concern). Kept at user-approved 1.0; configurable.

## Future Work (explicitly out of scope)

- Outdoor-compensated heat curve for the heating target (prerequisite for recommending the heating half broadly).
- Gain-schedule the cooling PID by (T_room - T_water) — the structural fix that makes water-temp changes composable with the learner.
- Bias the setpoint up under low aggregate demand (CentralController already aggregates) to avoid HP short-cycling.
- `dew_point_limited` binary sensor for dehumidifier/HRV automation (partially covered by the diagnostic sensor's binding_constraint).
