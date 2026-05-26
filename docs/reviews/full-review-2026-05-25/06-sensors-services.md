# Sensors, Services & State Attributes Review

Scope: `sensor.py`, `sensors/*.py`, `services/*.py`, `number.py`, `solar/solar_gain.py`, `analytics/reports.py`, `managers/state_attributes.py`, `managers/state_restorer.py`, `managers/status_manager.py`.

## Critical (must fix)

- **services/scheduled.py:191-194** — Uses `dt_util.utcnow()` to compute the ISO week number for the *current* week, then immediately stores `WeeklySnapshot(year=year, week_number=week_number, ...)`. The week the report covers is the prior 7 days, but `isocalendar()` of `end_date` reports the current week. So Sunday-morning runs (per `async_scheduled_weekly_report`, weekday 6) tag the report with the wrong ISO week (snapshot is named "week N" but actually covers week N-1). `HistoryStore.get_previous_week()` then collides with the next run. Use `(end_date - timedelta(days=1)).isocalendar()` or derive week from `start_date`.

- **services/scheduled.py:340** — `confidence_raw if adaptive_learner else None` references `confidence_raw` outside the `if adaptive_learner:` block at line 239. When `adaptive_learner` is `None`, evaluation short-circuits, but when an earlier zone in the loop had a learner and a later one does not, the stale `confidence_raw` from the previous iteration leaks into the new `ZoneSnapshot`. Initialize `confidence_raw = None` per-zone at the top of each loop body.

- **managers/state_attributes.py:639-645** — `_build_status_attribute` constructs a *new* `StatusManager` on every state-attribute read (i.e. every state write) instead of using `thermostat._status_manager`. Comment on line 637 acknowledges this is "for test compatibility". That is a smell that shouldn't ship: it (1) wastes allocations on every poll, (2) means the manager has no chance to maintain internal state across calls, and (3) re-runs `set_night_setback_controller` constantly. Fix tests instead — use the cached `thermostat._status_manager`.

- **managers/state_attributes.py:772** — Calls `thermostat._calculate_night_setback_adjustment()` (an internal method on the climate entity) to extract `cooling_supply_clamp` info. That method may invoke `_night_setback_controller.calculate_night_setback_adjustment(None)` which uses `dt_util.utcnow()` — a *second* time per attribute read after the same call inside `_build_status_attribute` line 734. The two calls can return different `in_night`/`info` values if the call straddles a setback boundary, producing internally inconsistent override entries. Cache the result once and reuse.

- **managers/state_attributes.py (whole file, 813 lines)** — Violates CLAUDE.md hard limit of 800 lines. Extract `_build_status_attribute` (~205 lines) into a separate module (e.g., `managers/status_attribute_builder.py`); it has no shared state with the other builders and is already factored.

- **sensors/energy.py:495-497** — `WeeklyCostSensor.native_unit_of_measurement` returns `self._currency` which is parsed at runtime from the cost entity's UoM at line 526-528 via `uom.split("/")[0]`. For an entity reporting `"$/kWh"` this yields `"$"`; for `"€"` (no slash, currency only) it never updates and stays `"EUR"`. Worse: `SensorDeviceClass.MONETARY` requires the UoM to be an ISO 4217 code (USD/EUR/GBP/etc.) — `"$"` is invalid and HA will emit a validation warning and may drop the entity from the recorder/statistics. Either validate against ISO codes or drop `device_class=MONETARY`.

- **sensors/energy.py:447-476** — `_check_week_boundary` uses raw `dt_util.utcnow()` and ISO `isocalendar()` for "Sunday rollover". The docstring says "Resets on Sunday midnight" but ISO weeks start on **Monday**. With UTC time, week boundaries cross at Sunday 23:59 UTC → Monday 00:00 UTC, not at the user's local Sunday midnight, and not at "Sunday" in any conventional sense. For users in negative UTC offsets this fires Sunday afternoon. Use `dt_util.now()` (local) and a fixed weekday, or document the actual behavior.

- **sensors/energy.py:533-572** — `WeeklyCostSensor.async_update` runs each scheduler tick but the sensor is only created if `energy_meter` was set at *first zone setup* (sensor.py:137-148). The check `hass.data[DOMAIN].get("system_sensors_created")` is one-shot, so the sensor is missing if the meter is configured later or if zone setup discovery info changes. There is no entity-state listener on `self._energy_meter_entity`, so the cost only updates every 5 minutes — for a fast-changing kWh meter this is acceptable, but on `STATE_UNAVAILABLE` the entity goes unavailable and accumulator can desync silently.

## High

- **state_attributes.py:104-108** — Comment says "legacy - will be moved to debug later" yet `_add_preheat_attributes` and `_add_humidity_detection_attributes` still write flat top-level attrs (`preheat_active`, `preheat_scheduled_start`, `preheat_estimated_duration_min`, `preheat_learning_confidence`, `preheat_observation_count`, `humidity_detection_state`, `humidity_resume_in`) to the unconditional attribute dict. Per CLAUDE.md, preheat/humidity belong in the `debug` group, and per the doc only `preheat_active`, `preheat_scheduled_start`, etc. are "debug only". The current code (a) violates the documented schema, (b) emits these even when `debug=False` for humidity, (c) gates preheat behind `debug` but writes the flat name not the grouped `debug.preheat.*`.

- **state_attributes.py:443-457** — `_add_humidity_detection_attributes` writes `humidity_detection_state` and `humidity_resume_in` regardless of debug mode. CLAUDE.md says humidity belongs under `debug.humidity` or under `status.overrides[].humidity`. The flat `humidity_resume_in` is a duration int (seconds) while the override field is `resume_at` ISO8601 — two representations of the same data is a bug magnet.

- **state_attributes.py:65-75** — `pid_history` is emitted as a flat top-level attribute on every state write. Each entry is a 6-field dict. If history grows past ~50 entries this attribute alone serializes >2KB per state change to the SQLite recorder. There's no truncation visible at this layer. Verify `gains_manager.get_history()` enforces a hard cap (e.g., last 100 entries) before serialization, otherwise recorder bloat is a real concern.

- **services/scheduled.py:191** — `start_date = end_date - timedelta(days=7)` but `WeeklyReport.format_markdown_report` uses `start_date.strftime("%b %-d")`. The `%-d` flag is **non-portable** (Linux glibc + macOS only). On Windows or musl it raises `ValueError`. Replace with `start_date.day` interpolation.

- **services/__init__.py:413-414** — `SERVICE_RUN_LEARNING` and `SERVICE_PID_RECOMMENDATIONS` are registered **only when debug=true**. The names are exported in `__all__`, advertised in `services.yaml`, and documented as services. Users following docs will get "Service not found" errors with no actionable feedback. Either always register them, or document them as debug-only and remove from `services.yaml`.

- **services/__init__.py:218-219** — `async_handle_set_vacation_mode` reads `call.data["enabled"]` directly. The vacation schema at `__init__.py:434-439` marks `enabled` as `vol.Required`, so this is safe — but the manual key access bypasses the schema if a future refactor changes the schema. Use `.get("enabled", False)` defensively or document the schema dependency.

- **services/scheduled.py:482-484** — Defaults `current_kp=100.0, current_ki=0.01, current_kd=0.0` when reading from state attributes. If the climate entity exists but PID gains aren't yet exposed (e.g., gains_manager not initialized), this silently feeds **wrong gains** to `calculate_pid_adjustment`, which then returns recommendations based on fabricated baselines. The user will see "recommended Kp=1.5" against a current "100" baseline and panic. Skip the zone instead.

- **sensors/comfort.py:250, 288 / sensors/energy.py:94, 342 / sensors/health.py:111, 121 / services/scheduled.py:46, 56, 212, 222** — Sensor entity IDs are hardcoded as `f"sensor.{zone_id}_{name}"`. This assumes HA's entity_id mirrors unique_id, which is **not true** if the user renames the entity in the UI (entity_id can drift, unique_id is fixed). Use `entity_registry.async_get_entity_id("sensor", DOMAIN, unique_id)` instead, or — better — read values directly from the in-memory sensor instance through the coordinator.

- **sensors/energy.py:233** — `self._delta_t = supply_temp - return_temp if supply_temp > return_temp else None`. This silently drops `delta_t = 0` (legitimate idle state). The downstream `extra_state_attributes` then reports `delta_t_c: None` while heat_output reports a value — confusing. Use `max(0.0, supply - return)`.

- **sensors/energy.py:553-564** — Meter-reset detection assumes "current < week_start" means reset, but for fresh energy meters that start at 0 and rolled over from a high value (e.g., a 6-digit utility meter wrapping), this misclassifies a roll-over as a reset and forgets the legitimate week-to-date consumption. Track `last_meter_reading` (already done line 391) and require `current < last_meter_reading` (a drop within the week) before treating as reset.

- **solar/solar_gain.py:109-147** — `_get_season` uses calendar dates fixed to Northern Hemisphere. Southern Hemisphere users (Australia, Brazil, NZ, ZA) get inverted seasons: their summer (Dec-Feb) is labeled `WINTER`. The `seasonal_intensity` table at line 260 then applies winter sun-angle reduction in their hottest month. This will silently destroy solar gain learning south of the equator. Either accept hemisphere config, or compute season from solar elevation rather than calendar.

- **solar/solar_gain.py:217-242** — `_get_cloud_adjustment` divides `actual_factor / learned_factor`. If the learned pattern is from `OVERCAST` (factor 0.1) and actual is `CLEAR` (factor 1.0), the adjustment is 10x — likely wildly overshooting actual gain. Cloud cover is multiplicative on baseline irradiance; once learned from overcast, the baseline is unknown and cannot be back-extrapolated. Skip patterns from clouded sessions when the actual is clearer, or cap the adjustment factor.

- **managers/state_attributes.py:760-761** — `learning_grace_until = grace_end.isoformat()` reads `_learning_grace_end` directly via `getattr` (private attribute access). Couples state_attributes to NightSetbackManager internals; if the field is renamed, this silently returns `None` (no error, just missing data). Add a public property `learning_grace_end` on the manager.

- **state_restorer.py:99-100** — `thermostat.set_hvac_mode(old_state.state)` passes the **state string** ("heat"/"cool"/"off"/"unavailable") to a setter that probably expects an `HVACMode` enum. If `old_state.state == "unavailable"` (entity was offline at shutdown), this passes "unavailable" into HVAC mode setter which likely raises or silently no-ops. Validate `old_state.state in HVACMode.__members__` first.

## Medium

- **sensors/performance.py:122** — `deque(maxlen=7200)` documented as "max 1 change per second, 1 hour = 3600". A misbehaving heater (relay chatter from a faulty thermostat) could fire 50+ state changes/sec for tens of minutes; 7200 cap is reached quickly and the oldest *legitimate* baseline disappears, breaking the "keep one state before window_start" invariant. Add explicit chatter detection: drop changes <1s after the previous one.

- **sensors/performance.py:472** — Cycles `< 1.0 min` are silently dropped. For `forced_air` (PWM 3 min) this is fine, but for relay-controlled valves doing legitimate 30-second pulses this hides them. Make the threshold heating_type-aware.

- **sensors/performance.py:399-405** — `extra_state_attributes` returns `last_cycle_time_minutes` only if `last_cycle_time` is truthy, but `0.0` is falsy and would be dropped. Use `is not None`.

- **sensors/energy.py:519-530** — Currency parsing from cost entity UoM (`uom.split("/")[0]`) is fragile and updates `self._currency` on every update. If the cost entity briefly returns `unknown` then comes back with a different UoM (rare but possible during HA restart), the currency silently changes — for `device_class=MONETARY` this triggers HA to invalidate historical statistics.

- **sensors/energy.py:545-548** — `from ..analytics.energy import UNIT_CONVERSIONS` inside the method. The lookup uses `unit.upper()` but the dict at `analytics/energy.py:9-13` keys are `"GJ"`, `"KWH"`, `"MWH"`, `"WH"`. `"BTU"` is mentioned in user docs but missing from the table → silently falls back to `1.0` conversion factor, producing a 3412x error.

- **sensors/health.py:64-74** — `zone_issues` exposes a nested dict-of-dicts with `severity`, `type`, `message` on **every** state write. For a misbehaving system with many issues, this can dwarf the rest of the state. Cap the number of issues per zone in the attribute (full list still available via service call).

- **sensors/health.py:139-143** — Constructs `zones_data` with `sensor_available=True` only when climate state is *unknown/unavailable*; the truthy default for missing climate is `True`. Inverted: when `climate_entity_id` is `None`, `sensor_available` defaults to `True` (wrong — there's no sensor at all). Default to `False` and set `True` only when verified available.

- **sensors/comfort.py:217** — `self._state = round(comfort_score, 0)` — `round(x, 0)` returns a float (e.g., `87.0`). With `state_class=MEASUREMENT` HA will show "87.0" instead of "87". Use `int(round(comfort_score))` and drop the `.0`. Also: there is no `native_unit_of_measurement` set — for a 0-100 score, set `PERCENTAGE`.

- **sensors/comfort.py:232** — Hardcoded "0°C deviation = 100, 2°C deviation = 0" linear formula. For floor_hydronic with 0.5°C tolerance this is too lenient; for forced_air with 0.15°C threshold this is too strict. Scale by heating type's convergence threshold.

- **services/scheduled.py:437-438** — `if _now.weekday() != 6: return`. Hardcoded Sunday. ISO weekday for Sunday is `6` (correct for `datetime.weekday()`). Add a comment explaining this isn't `isoweekday()` (which is 7).

- **services/scheduled.py:255-294** — `_compute_learning_status` is imported lazily inside the loop and called per-zone with manually-collected pause flags. The logic to detect pause conditions (`in_learning_grace_period`, `is_any_contact_open`, `should_pause`) is **duplicated** from `state_attributes.py:248-267`. Extract a `get_is_paused(thermostat)` helper.

- **sensors/actuator_wear.py:140** — `self._current_cycles = climate_state.attributes.get(attr_name, 0)`. No type coercion; if the attribute is `None` (explicitly nulled), arithmetic on line 144 raises `TypeError`. Add `int(... or 0)`.

- **sensors/actuator_wear.py:163-179** — Fires `actuator_maintenance_alert` event on **every** climate state change once threshold is crossed. A noisy climate entity could flood the event bus with hundreds of duplicate alerts per hour. Track last-fired timestamp and rate-limit to one alert per hour (or use a "level transition" pattern).

- **analytics/reports.py:195-196** — Same `%-d` portability issue as scheduled.py.

- **analytics/reports.py:43** — `display_name` does `self.zone_id.replace("_", " ").title()`. If `zone_id` contains an entity-like prefix or area ID, the result is awkward (`Living_Room_Floor` → `Living Room Floor` is fine, but `bedroom_2nd_floor` → `Bedroom 2Nd Floor`). Prefer a zone_name lookup.

- **managers/status_manager.py:223** — `now = dt_util.now()` (local time), while elsewhere in the codebase resume timestamps use `dt_util.utcnow()` (UTC). `convert_setback_end` then calls `format_iso8601` which just `.isoformat()`s. A local-aware datetime serializes with local offset; a UTC datetime serializes with `+00:00`. Mixing the two in the same `status.overrides` payload gives users inconsistent timestamps. Standardize on UTC throughout.

- **managers/status_manager.py:178** — `return bool(self._humidity_detector and self._humidity_detector.should_pause())`. Wrapping in `bool()` is fine, but the truthy-check on the detector object conflates "missing" with "doesn't pause", which is the same here. OK functionally but flagging since `should_pause()` could theoretically return non-bool.

- **state_attributes.py:172-179** — Threshold scaling. The `scale * X / 100.0` math implies `CONFIDENCE_TIER_1` is in percent units (0-100) while `convergence_confidence` is 0.0-1.0. Verify const values; if `CONFIDENCE_TIER_1 = 40` (per CLAUDE.md) the math is correct. The cap `min(..., 0.95)` is correct but `tier_3 = CONFIDENCE_TIER_3 / 100.0` is brittle: if anyone bumps `CONFIDENCE_TIER_3` above 100 it silently becomes >1.0 and no status ever reaches "optimized". Add an `assert`-like clamp (raise `ValueError` per CLAUDE.md).

- **state_attributes.py:41-42** — Reads `heater_cycle_count` and `cooler_cycle_count` from `_heater_controller` properties, but `_heater_controller` can be `None` during early init. Conditional handles that. However, when `is_demand_switch` is True, `build_cycle_count` returns just `heater_count` — for a demand-switch user who later disables demand_switch and re-enables heater/cooler split, the restorer in state_restorer.py:178-184 treats the bare int as `{heater: N, cooler: 0}`. This is correct one-way but lossy.

- **number.py:67-68** — `self.hass.data[DOMAIN]["learning_window_days"] = int(value)`. No notification to subscribers. Scheduled tasks that captured `learning_window_days` at startup (services/scheduled.py:455 reads it) never see the update unless they re-read each tick. Verify `async_daily_learning` re-reads from `hass.data` each call.

- **number.py:48-49** — `min=1, max=30` is hardcoded. The default is `DEFAULT_LEARNING_WINDOW_DAYS` from const — verify it's within `[1, 30]`. Also no `device_class` on a time-duration number; `NumberDeviceClass` doesn't have one for days, so this is fine.

## Low

- **sensor.py:158-162** — `async_update_sensors` calls `await sensor.async_update()` then `sensor.async_write_ha_state()` in series for all sensors. If one sensor's update raises, the loop aborts and subsequent sensors never update. Wrap each in try/except.

- **sensor.py:18-40** — `from .sensors.performance import (...)` re-exports symbols (DEFAULT_DUTY_CYCLE_WINDOW etc.) that are not used in this file. Pyright will flag as unused imports. They're re-exported through `sensors/__init__.py`; remove the duplicates from `sensor.py`.

- **sensors/performance.py:151-157** — Reads `heater_entity_id` from climate attributes as either list or string. The climate entity stores `heater` as a single string by config schema. Defensive coding is fine; consider warning when receiving a list with >1 entries (we silently pick `[0]`).

- **sensors/performance.py:574** — `cycle.overshoot for cycle in adaptive_learner.cycle_history if cycle.overshoot is not None`. Iterates the full history every 5 minutes. For long sessions (1000+ cycles) this is wasteful. Limit to the last N (e.g., 20) cycles.

- **sensors/energy.py:300-301, sensors/performance.py:71-76** — `_coordinator` property does a `hass.data.get(...).get(...)` chain on **every access**. CLAUDE.md says to use a cached `_coordinator` property — this implementation does what's documented, but the lookup itself isn't cached. Cache once after first successful read.

- **sensors/comfort.py:236** — `oscillations * 10.0` — should probably accept a max of 10 oscillations for full penalty, but no documentation explains the constant. Add a named constant.

- **sensors/health.py:67** — `issue.severity.value` assumes `severity` is an enum. If `SystemHealthMonitor.check_all_zones` returns a string for severity (legacy code path), this raises `AttributeError`. Type-narrow.

- **sensors/actuator_wear.py:124-126** — `_async_climate_state_changed` schedules a task per state change. High-frequency state changes (PWM cycling) create many tasks. Debounce.

- **services/__init__.py:148-153, 311-318** — Bare `except Exception as e` catches and stringifies. The string includes the exception message, which for downstream errors could include entity IDs or sensor values. Probably benign here but flag for privacy review.

- **services/__init__.py:125-127** — Percent-change math doesn't guard against tiny denominators: `current_ki = 0.001`, `recommendation.ki = 0.002` → 100% change. Cosmetic; users may panic. Round to fewer decimals or label as "small change".

- **services/scheduled.py:260-286** — Triple-nested try/except blocks just for `AttributeError`/`TypeError`. Simplify with `with contextlib.suppress(...)`.

- **managers/state_attributes.py:285-288** — `thermostat.hass.async_create_task(milestone_tracker.async_check_milestone(...))` is fire-and-forget — milestone exceptions are swallowed by HA's task wrapper. Use `hass.async_create_background_task(..., name=...)` (HA 2023.5+) for visibility.

- **managers/state_attributes.py:367-376** — `isinstance(current_temp, (int, float))` excludes `Decimal` and `numpy` scalars. Probably fine for climate temps, but the explicit "not MagicMock" comment suggests this is a test workaround that leaked into production. Move the MagicMock guard to tests.

- **managers/status_manager.py:181-190** — `format_iso8601` is a one-line wrapper around `.isoformat()`. Worth keeping for "intent documentation", but consider inlining or making it enforce UTC explicitly (`dt.astimezone(UTC).isoformat()`).

- **state_restorer.py:130** — `isinstance(integral_value, (float, int))` excludes `bool` correctly? Actually `bool` *is* a subclass of `int` in Python, so a restored bool integral value (unlikely but possible) would pass through. Add explicit `not isinstance(integral_value, bool)` guard.

- **analytics/reports.py:225** — `"All zones progressing normally"` is hardcoded English. No i18n hook. Acceptable for now but flag for localization plan.

## Architectural observations

- **state_attributes.py duplication of pause detection**: The "is_paused" computation (learning_grace_period + contact_open + humidity should_pause) is implemented at least three times: `state_attributes.py:248-267`, `services/scheduled.py:257-286`, and `status_manager.is_paused()`. Promote to a single `PauseDetector` and reuse. Currently the three implementations differ subtly (e.g., scheduled.py doesn't check `_humidity_detector` mode-awareness; status_manager.py does).

- **state_attributes.py as a god module**: 813 lines mixing builder functions (`build_cycle_count`, `build_learning_object`, `build_debug_object`) with rich `_build_status_attribute` orchestration and three `_add_*` injection functions. The pure builders are testable; the orchestration is not. Split into `state_attributes/builders.py` (pure), `state_attributes/orchestration.py` (impure).

- **Sensor entity-ID coupling**: Multiple sensors and the weekly report read peer-sensor values via `hass.states.get(f"sensor.{zone_id}_{name}")`. This creates a hidden runtime dependency graph and brittleness when users rename entities. Replace with direct method calls on the sensor instance via coordinator or a shared registry.

- **No formal sensor unit testing**: Many calculations (duty cycle, comfort score, week-boundary, meter-reset) have no obvious test coverage in the listed test files (test list in CLAUDE.md). Recommend adding `test_sensors_energy.py`, `test_sensors_performance.py` with mocked states.

- **Service result return values**: `async_handle_run_learning` and `async_handle_pid_recommendations` return rich dicts. HA service calls that return data require `supports_response=SupportsResponse.OPTIONAL` on registration — the current `async_register` calls don't set this, so callers using `return_response=True` will receive nothing. Either register with response support or stop returning.

- **State attribute schema drift**: CLAUDE.md documents `humidity_pause_count`/`contact_pause_count` reset on snapshot, but these are reset by `climate.reset_pause_counters()` called from `services/scheduled.py:366-370` after the snapshot is saved. If snapshot save fails (line 363 raises), counters are never reset and next week's report double-counts. Wrap with try/finally so reset happens even on save failure.

- **WeeklyReport.to_dict drops fields**: `to_dict` at `analytics/reports.py:230-246` omits `recovery_cycles`, `humidity_pauses`, `contact_pauses`, `comfort_score_prev`, `learning_status_prev`. If anything depends on `to_dict` for serialization (e.g., debug logging, persistence), this is silent data loss. Mirror the dataclass fields exhaustively.

## Positive observations

- Listener cleanup (`async_will_remove_from_hass`) is consistently implemented across sensors that subscribe to state changes — no leaks on entity removal.
- `dt_util.utcnow()` used consistently (no `datetime.now()` or `time.time()` in scope).
- No `assert` statements in production code.
- No `Optional[X]` — PEP 604 `X | None` syntax used throughout, matching CLAUDE.md.
- `StateRestorer` cleanly separates restoration from build logic and handles legacy field names (`pid_i` → `integral`, `heater_cycle_count` → `cycle_count`).
- `build_overrides` correctly implements documented priority ordering (contact > humidity > open_window > cooling_clamp > preheating > night_setback > learning_grace) and matches CLAUDE.md schema for each override type.
- `WeeklyReport` separates problem detection (`has_problems`) from formatting cleanly; trivially testable.
- `SolarGainLearner._update_patterns` requires `len(gains) >= 2` before publishing a pattern — sensible noise floor.
- `WeeklyCostSensor` correctly persists week boundary state via `extra_state_attributes` for `RestoreEntity` round-trip.
- Type coercion in restorers uses try/except per field — partial restoration on corrupted attrs instead of total failure.

## File map (absolute paths)

- /Users/kleist/Sites/ha-adaptive-climate/custom_components/adaptive_climate/sensor.py
- /Users/kleist/Sites/ha-adaptive-climate/custom_components/adaptive_climate/sensors/__init__.py
- /Users/kleist/Sites/ha-adaptive-climate/custom_components/adaptive_climate/sensors/performance.py
- /Users/kleist/Sites/ha-adaptive-climate/custom_components/adaptive_climate/sensors/energy.py
- /Users/kleist/Sites/ha-adaptive-climate/custom_components/adaptive_climate/sensors/comfort.py
- /Users/kleist/Sites/ha-adaptive-climate/custom_components/adaptive_climate/sensors/health.py
- /Users/kleist/Sites/ha-adaptive-climate/custom_components/adaptive_climate/sensors/actuator_wear.py
- /Users/kleist/Sites/ha-adaptive-climate/custom_components/adaptive_climate/services/__init__.py
- /Users/kleist/Sites/ha-adaptive-climate/custom_components/adaptive_climate/services/scheduled.py
- /Users/kleist/Sites/ha-adaptive-climate/custom_components/adaptive_climate/number.py
- /Users/kleist/Sites/ha-adaptive-climate/custom_components/adaptive_climate/solar/solar_gain.py
- /Users/kleist/Sites/ha-adaptive-climate/custom_components/adaptive_climate/analytics/reports.py
- /Users/kleist/Sites/ha-adaptive-climate/custom_components/adaptive_climate/managers/state_attributes.py
- /Users/kleist/Sites/ha-adaptive-climate/custom_components/adaptive_climate/managers/state_restorer.py
- /Users/kleist/Sites/ha-adaptive-climate/custom_components/adaptive_climate/managers/status_manager.py
