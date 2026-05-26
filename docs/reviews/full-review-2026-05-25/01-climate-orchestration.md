# Climate Orchestration Review

Files reviewed:
- `custom_components/adaptive_climate/climate.py` (1938 lines)
- `custom_components/adaptive_climate/climate_setup.py` (448)
- `custom_components/adaptive_climate/climate_init.py` (382)
- `custom_components/adaptive_climate/climate_control.py` (389)
- `custom_components/adaptive_climate/climate_handlers.py` (325)
- `custom_components/adaptive_climate/protocols.py` (429)
- `custom_components/adaptive_climate/const.py` (1114)
- `custom_components/adaptive_climate/__init__.py` (877)

---

## Critical (must fix)

- **climate.py:1102–1166 vs climate_control.py:31 — HVAC mode switch is not lock-protected, racing the control loop.**
  `async_set_hvac_mode` does not acquire `self._temp_lock`. It awaits `_async_heater_turn_off(force=True)` at line 1121 *before* mutating `self._hvac_mode`. While that await yields, a scheduled `_async_control_heating` (interval timer at `_setup_state_listeners` line 787) can fire, take `_temp_lock`, observe the **old** `_hvac_mode` (still HEAT/COOL), recompute PID, and turn the heater back ON. When `async_set_hvac_mode` resumes it writes `_hvac_mode=OFF`, but the actuator is now ON with no further trigger to turn it off until the next interval. Same issue exists for `async_set_temperature`, `async_set_preset_mode`, `clear_integral`, and the PID-tuning service handlers — all mutate shared state without the lock. Fix: acquire `self._temp_lock` around the entire mode/temp/PID mutation, or set `_hvac_mode=OFF` *first* (before turning off the heater) so a racing control loop short-circuits at the OFF check in climate_control.py:41.

- **climate_setup.py:332 + climate.py:332 — `valve_actuation_time` is stored as float seconds, then `+= int(self._transport_delay * 60)` is added in `_effective_min_on_seconds`. `climate_init.py:98` passes that float to `HeaterController(... valve_actuation_time=...)`.**
  `HeaterController.effective_min_on_seconds()` (heater_controller.py:436) returns `self._min_open_time + self._valve_actuation_time + self._transport_delay`, all summed in **seconds**, but `_query_and_mark_manifold` (climate.py:1859) calls `self._pid_controller.set_transport_delay(delay)` with `delay` in **minutes** (from `coordinator.get_transport_delay_for_zone` which returns minutes per its docstring), while `climate_control.py:344` calls `self._heater_controller.set_transport_delay(transport_delay_minutes * 60)` (seconds). Two callers, two different units, same setter on PID controller vs heater controller — easy to wire wrong. Verify which expects which; today PID controller likely gets minutes treated as seconds.

- **climate_control.py:343 — passes slug `self._zone_id` to `coordinator.get_transport_delay_for_zone` which then looks the value up in `_manifold_registry` keyed by **entity_id**.**
  Manifold schema (`__init__.py:191`) uses `cv.entity_id` for `zones`, so the registry's `_zone_to_manifold` dict is keyed by `climate.<slug>`. `coordinator.get_transport_delay_for_zone(self._zone_id)` then calls `self._manifold_registry.get_transport_delay(zone_id, …)` with the bare slug → `get_manifold_for_zone(slug)` returns `None` → silently returns 0 transport delay every cycle. Meanwhile `climate.py:1855` correctly passes `self.entity_id`. Inconsistent and one of them is broken. Pick one ID type and enforce it.

- **climate_setup.py:312–316 + climate.py:265–294 — three configured humidity options (`humidity_exit_threshold`, `humidity_exit_drop`, `humidity_max_pause_duration`) and the entity-level `sleep_temp` are accepted in schema/CLAUDE.md but never wired into `parameters` in `async_setup_platform`.**
  - `humidity_max_pause_duration` is read at climate.py:274 but never passed → silently default 3600s, ignoring user config.
  - `humidity_exit_threshold` / `humidity_exit_drop` schema in climate_setup.py:100–103 → never copied into `parameters` → climate.py:275–276 falls back to defaults.
  - `sleep_temp` is consumed at climate.py:143 but never passed by setup (nor present in domain config or schema). User cannot configure the documented `sleep` preset.
  Wire them through, or remove from schema/docs.

- **climate.py:1332–1338 — format spec on default `'N/A'` will raise `ValueError` mid-notification.**
  `f"Kp: {old_values.get('kp', 'N/A'):.4f}"` — Python's `.4f` format spec does not accept strings. If `old_values` is missing any of `kp/ki/kd`, the persistent-notification call raises and the auto-apply path partly succeeds (gains were already changed) but the user never sees the notification, and no log captures the failure context cleanly. Default to `0.0` and use a numeric format or guard with `if old_values.get('kp') is None`.

---

## High (should fix)

- **climate.py:823–837 — `_restore_state` and `_restore_pid_values` are dead compatibility wrappers.**
  Both build a fresh `StateRestorer(self)` each call and reach into `_restore_state` / `_restore_pid_values` (single-underscore private methods on StateRestorer). Nothing in the repository calls them (grep confirms). They also re-instantiate the restorer per call rather than using the one created in `async_added_to_hass`. Remove them or replace with a single delegating call to a cached restorer.

- **climate.py:530, 534, climate.py:1434–1438, climate_control.py:78–80, 192, 216, 219, 230 — pervasive reach-through into private attributes across module boundaries.**
  Examples:
  - `adaptive_learner._auto_apply_count`
  - `adaptive_learner._heating_rate_learner._active_session`
  - `adaptive_learner.undershoot_detector._consecutive_failures`
  This is exactly what the `ThermostatState` Protocol / manager interfaces were created to avoid (per CLAUDE.md: "Managers receive a `ThermostatState` Protocol, not raw callbacks or thermostat references"). Either:
  1. Expose proper public accessors on `AdaptiveLearner` / `HeatingRateLearner` / `UndershootDetector`, or
  2. Move the entire heating-rate-session lifecycle decision logic into `AdaptiveLearner` and just call a high-level method from climate_control.

- **climate_init.py:199 — `learning_gate._night_setback_controller = thermostat._night_setback_controller` patches a private attribute after construction to break a constructor cycle.**
  Symptom of a manager constructor accepting `None` then being patched. Add a public `set_night_setback_controller()` (mirrors how `StatusManager.set_night_setback_controller` is done in climate.py:478) or restructure construction order so the gate is built after the manager.

- **climate.py:782–787 — control-loop interval timer registration uses `self._sampling_period > 0` for fallback, but `_sampling_period` defaults to `00:00:00` → `0`, so it always falls back to `DEFAULT_CONTROL_INTERVAL=60s` unless explicit.**
  Combined with the comment "explicit control_interval > sampling_period > default 60s", this means setting only `sampling_period: 30` does what the comment promises. But `sampling_period` is also stored as `self._sampling_period` (seconds) and passed to `PID(sampling_period=...)` at line 443 — a zero sampling period passed to the PID likely affects integral accumulation math. Verify PID handles zero sample period gracefully; otherwise this is a hidden footgun.

- **climate.py:102, 103, 405 — `kwargs.get("sampling_period").seconds` etc. will `AttributeError` if the platform schema is bypassed (programmatic creation, tests).**
  Voluptuous gives defaults at the platform layer, but `AdaptiveThermostat(**parameters)` can be constructed directly. Use `(kwargs.get("sampling_period") or DEFAULT).total_seconds()`. Also note: `timedelta.seconds` truncates anything ≥ 1 day. A user-configured `sensor_stall: "30:00:00"` (30 h) silently becomes 21600 (6 h). Always use `total_seconds()`.

- **climate.py:539, 639, 862, 1169, 1404, 1865 — direct `self.hass.data.get(DOMAIN, {}).get(...)` violates CLAUDE.md ("never inline `hass.data.get(DOMAIN, {}).get('coordinator')` — use cached property").**
  `self._coordinator` is the cached property, but the rule applies to `manifold_registry`, `learning_store`, `mode_sync`, `set_integral_unsub`, etc. as well. Add accessors (`self._manifold_registry`, `self._learning_store`, etc.) or a typed `DomainData` object stored on coordinator. The same pattern repeats in `climate_control.py:56,65,341` and `climate_init.py:241`.

- **climate.py:1893 (and 1879–1881) — duplicated transport-delay reset.**
  `_async_heater_turn_off` resets `_transport_delay` AND `_on_heating_ended_event` also resets it. If HEATING_ENDED fires after `_async_heater_turn_off`, the second call is a no-op because `_transport_delay is None`. But if the event ever fires *before* (e.g., emitted by HeaterController right at the start of turn-off), the dead-time reset happens twice. Race-prone. Pick one place.

- **climate.py:783 — `self._async_control_heating` is registered as the time-interval callback, but its signature is `(self, time_func, calc_pid=False, is_temp_sensor_update=False)` with `time_func` defaulting to None.**
  `async_track_time_interval` passes the current datetime positionally, so `time_func` gets the datetime. This value is then never used — fine — but the parameter is typed `object` (climate_control.py:28). Type as `datetime | None`, document, or remove.

- **climate_handlers.py:35–37 vs 233–243 — `_async_sensor_changed` always updates `_previous_temp_time = _cur_temp_time; _cur_temp_time = time.monotonic()` BEFORE calling `_async_update_temp`, which may early-return on UNAVAILABLE/UNKNOWN.**
  Effect: when the sensor goes unavailable, the PID's dt window advances even though no new reading occurred. The next valid reading then computes derivative across a stretched timebase but with a stale-vs-new value, producing a derivative kick. Move the timestamp updates *after* a successful temp parse.

- **climate.py:1755 — duty accumulator reset uses `abs(value - old_temp) > 0.5` magic number.**
  Should be a named constant; also inconsistent with the cycle reset rules elsewhere that use heating-type-aware thresholds (recovery threshold 0.3 vs 0.5 in climate_control.py:238).

- **climate.py:1077 — broken type annotation: `set_hvac_mode(self, hvac_mode: (HVACMode, str))`.**
  Tuple where union was meant; pyright would treat as `tuple[type[HVACMode], type[str]]`. Should be `HVACMode | str`.

- **climate.py:586–606 — `_async_assign_label` and `_async_assign_area` blow away user customisations on every restart.**
  - `entity_registry.async_update_entity(self.entity_id, labels={label.label_id})` *replaces* the labels set, so any other label the user added by hand is removed on every HA restart. Read existing labels, union with the integration label, write the union.
  - `_async_assign_area` similarly clobbers a user-chosen area each restart. Only assign if entity has no area, or only on first registration.

- **climate_setup.py:204 — `assert platform` in production code.**
  CLAUDE.md: "Never use `assert` in production". On `python -O` asserts are stripped → `platform.async_register_entity_service` then crashes with AttributeError on None. Raise `RuntimeError("platform not initialized")` instead.

- **climate.py:297 — local import of `StatusManager` inside `__init__`, with the manager unconditionally constructed regardless of feature flags.**
  Move to module-level imports (consistent with NightSetback, HumidityDetector at file top). The import-inside-init pattern hides import errors until entity creation.

---

## Medium (worth fixing)

- **climate.py:1938 lines — exceeds CLAUDE.md's 800-line cap by 2.4×.**
  Two ClimateXxxMixin files were extracted but the bulk of orchestration, restoration, PID-history services, and event handlers stayed in climate.py. Further extraction candidates: (a) preheat/heating-rate cycle handlers (1358–1483) → adaptive/cycle_handlers, (b) PID-history service methods (1262–1292), (c) heater-control facade setters (1663–1738) → managers/state_callbacks.

- **climate.py:146–157 — `if True in [temp is not None for temp in [...]]:` is a famously awkward anti-pattern.**
  Should be `if any(temp is not None for temp in (...))`.

- **climate.py:1077–1100 — synchronous `set_hvac_mode` exists alongside the async version, with diverging behaviour.**
  The sync version doesn't reset integral on HEAT↔COOL, doesn't trigger mode-sync, doesn't emit ModeChangedEvent. If anything in HA calls the sync method (rare but possible during state restoration / lovelace card direct call), the entity ends up in an inconsistent state. Remove `set_hvac_mode` or delegate to a shared sync core.

- **climate.py:1684–1687 — `_set_ke` is documented "legacy callback, now handled by gains_manager. pass". Dead method.**
  Remove. Same with `_set_target_temp` (line 1744–1770) sync side-effects — has logic mixed with state mutation; consider routing entirely through TemperatureManager events.

- **climate.py:106 — `self._saved_target_temp = kwargs.get("target_temp") or kwargs.get("away_temp")`.**
  Falsy 0 would be treated as missing. Unlikely in practice (target 0°C) but use `target_temp if target_temp is not None else away_temp`.

- **climate.py:1077 + 1087/1130 — `HEAT_COOL` is allowed by setter but absent from `_attr_hvac_modes`.**
  Setting HEAT_COOL via the climate service would partially work (internal state set) but UI/services treat it as unsupported. Add explicit rejection or include in modes.

- **climate.py:329–330, 1922–1933 — pause counters are entity-level mutable counters incremented from handlers and reset from a service.**
  No lock, but since HA is single-threaded async this is safe. The counter is incremented on *every* sensor open transition, but a single "pause" event aggregates multiple sensors (any-open). So with N sensors all opening together, the counter +=N for a single user-visible pause. Either count actual paused transitions (any→none / none→any) or rename to `contact_open_events`.

- **climate_control.py:118–128 — `TemperatureUpdateEvent` is emitted on **every** control-loop call once `_current_temp` and `_target_temp` are non-None, even when nothing changed.**
  At a 60s control interval this is benign; with shorter intervals it spams subscribers. Consider emitting only when temp or setpoint actually changed.

- **climate_control.py:91–93 — humidity decay uses `time.monotonic() - self._last_control_time` and applies `0.9 ** (elapsed/60)`.**
  If `_last_control_time` was never set (first call after pause begins), `elapsed` could be the entire HA uptime → integral collapses to ~0 instantly. Guard with sane lower bound on elapsed (e.g., min(elapsed, 600s)).

- **climate.py:1381 — `if start_temp and end_temp and duration_minutes and outdoor_temp is not None:` mixes falsy and `is not None`.**
  A target of 0.0°C, 0-minute duration, or 0°C outdoor are all valid but treated as missing. Use explicit `is not None` for all four.

- **climate_init.py:104–139 — `stored_preheat_data` and `stored_ke_data` are read from `zone_data` but never popped after restoration.**
  They sit in coordinator.zone_data forever as duplicate state. Pop after use.

- **climate_init.py:166–173 — closure `get_adaptive_learner` re-resolves coordinator/zone_data on every call.**
  Cheap, but inconsistent with the cached `_coordinator` property pattern, and `coordinator` is captured at closure time anyway. Cache `adaptive_learner` if it's stable, or fall back to fresh lookup only on first failure.

- **climate.py:1496–1513, climate.py:1494, climate_control.py:14, climate.py:32–37 — many imports done inside functions (e.g. `from .const import PIDChangeReason` inside `_check_physics_rate_and_boost_ki`).**
  No circular-import reason for half of these. Move to module top to surface failures at load.

- **climate_setup.py:328–332 — `valve_actuation_config.total_seconds()` returns float; `HEATING_TYPE_VALVE_DEFAULTS.get(..., 0)` returns int. Variable typed as union of int|float silently.**
  Cast to int (seconds resolution) before storing on entity to avoid later float-vs-int comparisons.

- **climate.py:1185–1191 — `ModeChangedEvent` emitted only after the mode change finishes successfully, but the previous `await self._async_heater_turn_off(force=True)` (line 1121) can swallow exceptions.**
  Subscribers expecting to react to mode-off transitions might miss the event if the turn-off raised.

- **climate.py:1245 — `_ke_controller is not None` guard but no error if it's None. Silent failure of `async_apply_adaptive_ke`.**
  Either log or raise.

---

## Low / nits

- **climate.py:11 — `# ABC removed - no abstract methods in this class` — dead comment, remove.**
- **climate.py:7 — `from datetime import datetime, timedelta`. `datetime` only used as type hint at line 326 (`dict[str, datetime]`). With `from __future__ import annotations` it's fine, but consider TYPE_CHECKING-only import.
- **climate.py:20–22 — `INPUT_NUMBER_DOMAIN` import + magic `NUMBER_DOMAIN = "number"` constant.** Document why the bare string is used (already done) but consider importing from `homeassistant.components.number.const` behind a try/except for cleanliness.
- **climate.py:78–79 — `from .climate_setup import async_setup_platform as async_setup_platform` (self-rename).** Comment explains it; consider `__all__ = ["async_setup_platform", "PLATFORM_SCHEMA"]` instead.
- **climate.py:213 — `_LOGGER.debug("%s: night_setback_config from kwargs: %s", ...)` logs full config dict.** Low-sensitivity, but if any time data is debug-relevant only, gate behind `if _LOGGER.isEnabledFor(logging.DEBUG)`.
- **climate.py:840 — `def should_poll(self): return False`. Property type should be `bool`. Trivial.
- **climate.py:1063 — `if getattr(self, "_pid_controller", None) is not None:` — the entity always has `_pid_controller` set in `__init__`. The `getattr` guard suggests legacy worry; can drop.
- **climate.py:1096 — `if self._pid_controller is not None:  # pyright: ignore[reportUnnecessaryComparison]`.** Bare pyright ignore is fine but explain *why* it's necessary (pyright thinks attribute is always-set so flags this). Good practice per CLAUDE.md to add the explicit code, which is done — but the comment is missing the "because" justification.
- **climate.py:1328 / 1599 — emoji in user-facing notification titles (🔧, ⚠️).** Per CLAUDE.md the project says "Only use emojis if the user explicitly requests it." User-facing strings are arguably out of scope, but call it out.
- **climate.py:402–403 — `self._preheat_cycle_unsub = None` typed implicitly.** Should be `: Callable[[], None] | None`.
- **climate.py:407 — `self._p = self._i = self._d = self._e = self._dt = 0` mixes int and float-typed fields.** Should be 0.0.
- **climate.py:1567 — `adaptive_learner.undershoot_detector.cumulative_ki_multiplier *= suggested_boost` mutates a manager-owned counter from the orchestration layer.** Encapsulate.
- **climate_handlers.py:147, 177, 230 — `await self._async_control_heating(calc_pid=False, ...)` in handlers that do tens of fields of work; consider `hass.async_create_task` if the handler is hot.
- **climate_setup.py:208 — `zone_id = slugify(name)` with no de-duplication check.** Two zones with names that slugify to the same string silently collide in coordinator registration.
- **climate_init.py:38 — `_LOGGER = logging.getLogger(__name__)` — fine, but `_LOGGER.info` is used in setup paths that run once per zone. Acceptable.
- **__init__.py:7 — `from datetime import datetime, timedelta` and `from typing import Any`. Neither symbol used outside of stubs.** Cleanup.
- **__init__.py:680–694 — `_handle_set_integral_event` reaches into `_pid_controller.integral` and `_i` directly without lock or async-write.** Race with control loop. Should call a public `async_set_integral(value)` on the entity.
- **protocols.py:133 — `_hvac_mode: HVACMode` but actual entity allows `HVACMode | None`** (line 549 initialises to None pre-restoration). Protocol should match `HVACMode | None`.
- **protocols.py:353 — `def _calculate_night_setback_adjustment(self) -> tuple:` untyped tuple.** Use `tuple[float | None, bool, dict]`.
- **protocols.py:427 — `_gains_manager(self) -> object` — typed as bare `object`.** Should be `PIDGainsManager` from a TYPE_CHECKING import.

---

## Architectural observations

1. **AdaptiveThermostat is a god object.** ~1940 lines mixing entity-platform plumbing, restoration, manager wiring, service handlers, event subscribers, and 20+ setter callbacks used by managers. The mixin split (`ClimateControlMixin`, `ClimateHandlersMixin`) only moves code without solving the cohesion problem — the mixins still reach into `self._*` private attributes belonging to the host class. Real fix: each manager owns its state, exposes a typed interface, and the entity just dispatches.

2. **`ThermostatState` Protocol is largely vestigial.** Despite the Protocol existing, callers consistently bypass it (climate_init wires lambdas instead of passing `self` typed as a Protocol; climate_control reaches into `adaptive_learner._heating_rate_learner._active_session`). Either commit to the Protocol (no private attribute access across modules, no lambda capture of internal state) or remove the indirection.

3. **Setter callback pattern (`_set_p`, `_set_i`, …, `_set_target_temp`, `_set_force_on`, etc.) is busy-work indirection.** Each manager gets handed a closure pointing at a one-line setter on the host. This was a workaround for not being able to pass `self`, but the host is passed to many managers anyway (e.g. `HeaterController(thermostat=thermostat, …)`, `ControlOutputManager(thermostat_state=thermostat)`). Pick one: either pass a typed Protocol facade, or pass `self` and have managers call `state.set_p(...)` on a defined ABC/Protocol.

4. **Multiple stores of truth for HVAC mode string.**
   `self._hvac_mode` (HVACMode enum), `self._hvac_mode.value` (string) computed inline ~15 times, plus `"off"` fallback strings sprinkled when None. Either centralise via a property (`hvac_mode_str -> str`) or store consistently. Bug surface: `self._hvac_mode.value if self._hvac_mode else None` vs `... else "off"` — inconsistent default across callers (climate.py:1173 uses "off"; climate_control.py:59 uses None).

5. **Restoration sequencing is fragile.** `async_added_to_hass` does: managers → status manager wiring → state listeners → restore from RestoreEntity → cycle_tracker → coordinator wiring → physics baseline → control loop kickoff. A failure in any step leaves the entity half-initialised but still receiving events (listeners are already attached). At minimum, attach listeners *last*.

6. **Manifold transport delay is wired through three separate code paths** (climate.py:1859 to PID controller, climate.py:1862 to cycle tracker, climate_control.py:344 to heater controller), each with its own unit assumption and its own coordinator lookup. Centralise — coordinator should push deltas to a single subscriber on each zone (e.g. via the existing CycleEventDispatcher) rather than each consumer polling.

7. **`asyncio.Lock` is the only synchronisation primitive but only one method takes it.** Either drop the lock (HA is single-threaded async, the lock only matters for cooperative re-entry across awaits) and document the invariants, or use it on every method that mutates control state. Half-measures invite Heisenbugs of the kind described in the Critical section.

8. **`climate_setup.py:237–324` `parameters` dict has 60+ fields and grew organically.** Build it incrementally from a typed dataclass (`AdaptiveThermostatConfig`) validated once with strict types — kwargs unpacking into `AdaptiveThermostat.__init__` defeats type checking.

9. **`protocols.py` exposes nearly the entire entity surface as a Protocol.** That defeats the Protocol's purpose; with 30 properties it's effectively documentation of the entity, not an interface. Slim to the methods actually called by managers (currently most lambdas just need `_current_temp`, `_target_temp`, `_hvac_mode`).

10. **Constants/defaults split across `const.py` and inline literals in the entity** (e.g. `0.5°C` setpoint-change threshold at climate.py:1755, `60` minute grace period at climate.py:946, `0.9` decay factor at climate_control.py:92). Move all tunables to const.py for discoverability and unified test coverage.
