# Multi-Zone Coordination Review

Scope: `coordinator.py`, `central_controller.py`, `managers/auto_mode_switching.py`,
`managers/night_setback_manager.py`, `managers/night_setback_calculator.py`,
`managers/notification_manager.py`, `managers/events.py`, plus protocols/helpers
for context.

## Critical (must fix)

- **managers/night_setback_calculator.py:112–114** — `get_weather_condition()` reads
  `coordinator._weather_entity`, an attribute that does not exist on the coordinator
  (the coordinator exposes a `weather_entity` *property* that resolves from
  `hass.data[DOMAIN]["weather_entity"]`). The first branch is therefore always
  false; the code only ever takes the hard-coded `weather.home / weather.knmi_home
  / weather.forecast_home` fallback, which silently breaks dynamic night-setback
  end-time calculation for any user whose weather entity has a different name.
  Fix: replace with `coordinator.weather_entity` (and guard for `None`).
  Also: this whole detour is unnecessary — `night_setback_calculator` should be
  given the weather entity via `__init__` (or read it from the injected
  coordinator) rather than reaching into `hass.data` with the wrong key.

- **coordinator.py:62–80 / 668–696** — `_setup_outdoor_temp_listener()` and the
  `_startup_eval_unsub` timer are scheduled inside `__init__`, but
  `async_cleanup()` is the only place that unsubscribes — and nothing in the
  integration calls `async_cleanup()` on unload. (`grep` for
  `async_cleanup`/`coordinator.async_cleanup` in `__init__.py` and elsewhere
  comes up empty.) Result: on every config-entry reload the old coordinator's
  state-change listener stays subscribed and the new coordinator adds another,
  leaking listeners (and EMA tasks/auto-mode tasks) for the lifetime of the HA
  process. Fix: wire `async_cleanup()` into `async_unload_entry` and also call
  `central_controller.async_cleanup()` from the same path.

- **coordinator.py:46** — `SunPositionCalculator.from_hass(hass)` is called
  synchronously from `__init__` (which runs in the event loop). If that helper
  performs any blocking I/O (timezone/zone.home lookups are usually cheap, but
  some implementations call `astral` setup with home coordinates) this should be
  audited; more importantly, the coordinator's `__init__` already touches
  `hass.states.get(weather_entity_id)` (via `self.outdoor_temp` on line 71) and
  `hass.data.get(DOMAIN, {}).get("house_energy_rating")` *before*
  `__init__.py` has had a chance to populate those keys on a cold start. On a
  fresh install the first coordinator may therefore be created with
  `_outdoor_temp_tau = 4.0` even when the user configured `A++`, and
  `_outdoor_temp_lagged = None`. Verify init ordering in `__init__.py`; if
  domain data is populated *after* coordinator construction, this is a real
  bug. Fix: move EMA-tau resolution and initial lag-temp seeding into an
  `async_setup()` / first-update method.

- **coordinator.py:347–375** — `update_zone_demand` (sync, called from
  `_async_control_heating`) compares `old_state != new_state` with both keys
  populated as the new dict, but does **no de-duplication beyond that**: if the
  same zone flips heating→cooling→heating in a single call-stack (sync mode
  change, mode propagation, immediate re-evaluation), the `_update_pending`
  single-flight guard prevents a second `CentralController.update()` from
  being scheduled. The pending task reads `get_aggregate_demand()` *once* when
  it runs — so any state change that occurred *after* `_update_pending` was set
  but *before* the task ran is captured correctly, **but** state changes that
  occur *during* the task body but *after* it has called
  `get_aggregate_demand()` are silently dropped (no follow-up scheduled).
  Symptom: rapid zone mode flips can leave the central heater on or off
  incorrectly until the next periodic update (30 s). Fix: turn
  `_update_pending` into a "rerun requested" flag — when a new demand change
  arrives while pending, set `_rerun_pending=True`; in `_update_with_guard`'s
  `finally`, if the flag is set, schedule another run.

- **coordinator.py:640–666 (`_apply_house_mode`)** — Iterates over
  `self._zones.items()` and `await self.hass.services.async_call(...)` for each
  zone. Each propagated `set_hvac_mode` will re-enter the climate entity,
  which will (via `ModeSync.on_mode_change`) try to sync the same mode back
  out. `ModeSync` does have a `_sync_in_progress` guard, but it is *only on
  the ModeSync instance*; `_apply_house_mode` does **not** consult or set that
  flag. So when auto-mode-switching propagates a mode to N zones, the *first*
  child zone's state-change re-enters `ModeSync.on_mode_change`,
  `_sync_in_progress` is False, and ModeSync starts a redundant fan-out to the
  other N-1 zones. Result: O(N) wasted service calls per auto-mode switch and
  a logged "synchronizing other zones" race against the original loop. Fix:
  acquire/set `mode_sync._sync_in_progress = True` (or use a dedicated
  cross-component re-entrancy lock) for the duration of `_apply_house_mode`.

- **managers/notification_manager.py:96, 105** — Uses `datetime.now()` for
  cooldown bookkeeping. Project rules require `dt_util.utcnow()` for
  wall-clock and `time.monotonic()` for elapsed durations. `datetime.now()`
  returns naive local time, so DST jumps or timezone changes will make
  cooldowns appear to elapse instantly (or never). For a *cooldown* the
  correct primitive is `time.monotonic()`; convert
  `_cooldowns` to `dict[str, float]` and compare against `time.monotonic()`.

- **central_controller.py:229–267** — `_cancel_heater_startup_unlocked` /
  `_cancel_cooler_startup_unlocked` release `self._startup_lock` mid-method
  to wait on the cancelled task (to avoid deadlock with the task's `finally`
  block). The pattern is fragile:
  1. The method is named `_unlocked` (meaning "caller holds the lock") but it
     actually releases and re-acquires the lock. Any caller that has cached
     invariants protected by the lock will see them violated across the
     release.
  2. After `self._startup_lock.release()` and before
     `self._startup_lock.acquire()`, a second `update()` can run, observe
     `_heater_waiting_for_startup` still True (the cancelled task hasn't
     reached its `finally` yet), bail out of the demand-check branch, and
     incorrectly conclude no work is needed.
  3. If the cancelled task has already passed `asyncio.sleep` and is sitting
     in `async with self._startup_lock:` at line 195, it will acquire the
     lock the moment we release it (line 239), run `_turn_on_switches` for
     a no-longer-current demand, and *then* enter its `finally` block.
  Fix: do not call `task.cancel()` while holding the lock at all. Refactor
  so the cancellation path is: snapshot the task reference, release the
  lock, cancel + await the task, then reacquire and clear the state fields.
  Even better, eliminate the manual lock dance entirely by gating the
  startup body on a check-then-act under the lock and using
  `asyncio.shield` / explicit cancellation outside the lock.

## High

- **coordinator.py:50, 372–375** — `_update_pending` is a plain bool mutated
  from both the event loop thread (only) but without any test that the task
  was actually scheduled successfully. If `async_create_task` raises (e.g.
  during HA shutdown) the flag stays True forever and no further central
  updates fire. Wrap in `try/except` and reset flag on failure, or use the
  rerun-pending pattern above.

- **coordinator.py:611–614** — `dt_seconds` is computed as
  `now - self._last_outdoor_temp_update` if non-None else `0`. Passing
  `dt_seconds=0` into `update_outdoor_temp_lagged` makes that method reset
  the EMA to the raw temperature (the `dt_seconds <= 0` branch overwrites
  `_outdoor_temp_lagged`). That happens on the very first weather update
  after restart (when `_last_outdoor_temp_update is None`), which is fine,
  but it *also* happens if two state-change events arrive in the same
  `time.monotonic()` tick (rare but possible during HA replay of buffered
  events). Effect: EMA loses history. Fix: when
  `self._last_outdoor_temp_update is None`, just seed the EMA without
  re-running the filter; otherwise use `max(dt_seconds, MIN_DT)` so a
  zero-dt event acts as a no-op rather than a reset.

- **coordinator.py:224–236 (`update_outdoor_temp_lagged`)** — Alpha is
  computed without clamping for very large `dt_seconds` *before* the
  `min(1.0, …)` clamp, which is OK numerically, but the formula
  `alpha = dt / tau` is the *Euler discretization* of a first-order filter
  and is only stable for `dt << tau`. With `tau=4h` (14 400 s), an event
  with `dt_seconds=3600` gives `alpha=0.25` (fine), but two consecutive
  events 6 h apart will overwrite the EMA almost entirely. For better
  fidelity under irregular sampling use `alpha = 1 - exp(-dt / (tau*3600))`.

- **coordinator.py:521–533 (`get_active_zone_setpoints`)** — Reads the
  *actual climate entity state's* `temperature` attribute via
  `hass.states.get`. (a) does a per-call import of `HVACMode` inside the
  method (minor), (b) returns the configured target_temperature of the
  zone's *climate entity* — which for an Adaptive Climate zone may itself
  be the night-setback-reduced effective target. Auto mode switching's
  median compares the *forecast* against this potentially-reduced target,
  which can flip the mode to HEAT around night-setback boundaries even when
  the user's daytime target is fine. Fix: store user setpoint
  (pre-setback) in zone_data or use the climate entity's `target_temp_high`
  / preset target rather than the current effective `temperature`
  attribute.

- **managers/auto_mode_switching.py:53** — `forecast_days` accepts the
  legacy `"forecast_hours"` alias via `or` chain, which collapses any
  falsy value (0 days, "") to the default. Use explicit
  `if x is not None` checks. More importantly: the alias name
  `forecast_hours` is misleading because the value is treated as *days*
  on line 164 (`forecast[: self._forecast_days]`). Either drop the
  legacy alias or convert hours→days when reading it.

- **managers/auto_mode_switching.py:175–268 (`async_evaluate`)** —
  `_last_switch` is updated on every successful evaluation, but the
  function returns the new mode and the caller
  (`coordinator._async_evaluate_auto_mode`) calls
  `_apply_house_mode`. If the apply fails (no zones, all OFF, service
  errors), `_last_switch` is still bumped and the user is locked out of
  re-evaluation for `min_switch_interval`. Fix: only update
  `_last_switch` after the caller confirms at least one zone was actually
  switched. Alternatively, expose a `mark_switched()` method called by
  the apply step.

- **managers/auto_mode_switching.py:286–304 (`get_state_attributes`)** —
  `get_median_setpoint()` is called from a sync `get_state_attributes` —
  fine — but reconstructs `last_switch_dt` by subtracting monotonic
  elapsed time from `dt_util.utcnow()`. This is wall-clock-correct, but
  the returned `next_allowed_switch.isoformat()` lacks a timezone — it
  inherits from `dt_util.utcnow()`, which is UTC-aware, so OK. However
  computing this on *every* attribute read is wasted work; cache the
  ISO strings and only recompute when `_last_switch` changes.

- **central_controller.py:269–311** — Turn-off debounce tasks
  (`_heater_turnoff_task` / `_cooler_turnoff_task`) are created from
  *inside* the lock-held context but their `finally` blocks (lines 336,
  361) reassign `self._heater_turnoff_task = None` **without** the lock.
  Reading/writing the same attribute from a sync `_cancel_*_unlocked`
  (which checks `_heater_turnoff_task.done()`) while it's being mutated
  in a task `finally` is a race. The race is benign on CPython (GIL +
  single-threaded event loop), but if multiple concurrent invocations of
  `update()` interleave, the `done()` check can pass on a task whose
  `finally` is still pending, leading to a double-schedule. Fix: clear
  the task field under the lock, e.g. wrap the assignment in
  `async with self._startup_lock:`.

- **central_controller.py:113–153 (`_update_heater` / `_update_cooler`)** —
  When `has_demand` becomes True, the code calls
  `_are_all_switches_on(self.main_heater_switch)`; if all are already on,
  the branch is skipped (no startup). But `_cancel_heater_turnoff_unlocked`
  is **only** called *before* the demand-on branch — never if the switches
  are already on, meaning a previously-scheduled turn-off can still fire
  even though demand returned. Trace: demand on → turnoff scheduled → 5 s
  later demand returns → all switches still on → branch skipped →
  turnoff fires at the 10 s mark. Fix: move
  `_cancel_heater_turnoff_unlocked()` above the
  `not _heater_waiting_for_startup and not _are_all_switches_on` check
  (already the case at line 122, **but** only inside the `if has_demand`
  branch with no early-return — re-verify by tracing the demand-on/all-on
  path: lines 121–128, `_cancel_heater_turnoff_unlocked()` runs first, so
  this race is actually already covered. **Downgrade to Low** if I have
  misread; the comment in the code reading "Cancel any pending turn-off
  (demand came back)" suggests intent matches. Leaving as a note for the
  next reviewer to walk through, as the read-twice/all-on edge is
  non-obvious.

- **coordinator.py:294–309 (`register_zone`)** — On duplicate
  registration the warning is logged and the new data overwrites the old
  zone_data, but `_demand_states[zone_id]` is **reset to
  `{"demand": False, "mode": None}`**. If a zone was actively
  heating at the time of re-registration (which happens during config
  reload), the central controller's next `get_aggregate_demand()` will
  see no demand for that zone and may shut off the boiler mid-cycle.
  Fix: only initialize `_demand_states[zone_id]` if not already present.

- **coordinator.py:340–344 (`unregister_zone`)** — Uses inline
  `self.hass.data.get(DOMAIN, {}).get("mode_sync")` rather than holding
  a cached reference. Acceptable, but inconsistent with CLAUDE.md's
  "use `self._coordinator`" guidance (which applies to the climate
  entity, not the coordinator itself — so this is technically OK). More
  important: nothing here removes the zone from the `central_controller`
  (it just stops appearing in `get_aggregate_demand` because it was
  dropped from `_demand_states`), nor from any thermal-group manager
  (`set_thermal_group_manager(manager)` stores a reference but the
  manager isn't consulted on zone removal). Verify thermal_group_manager
  is informed on zone unregister, or document the leak.

- **managers/night_setback_manager.py:248–269 (auto-learning setback)** —
  `should_apply_auto_learning_setback()` checks
  `self._calculator.is_configured` and bails out if so, so this branch is
  only reachable when the user has *no* night setback configured. But the
  returned tuple is `(effective_target, True, info)` — the `True` says
  "in night period" even though the user never configured one.
  Downstream code (e.g. `_apply_night_setback_to_target` in climate.py,
  plus learning-grace logic) will treat this as a regular night setback
  transition. If `_night_setback_was_active` flips on/off across the
  auto-learning window each day, the system will set a 60-minute learning
  grace period twice a day for users who have **never opted in to night
  setback**. Fix: the auto-learning path should set its own pending
  transition / grace logic and not piggyback on the regular path's
  `True`/`False` semantic. Also: `info` is missing
  `night_setback_end` — downstream attribute consumers may KeyError.

- **managers/night_setback_manager.py:261** —
  `(current_time - self._last_auto_setback).days > 0` — `timedelta.days`
  on a sub-24h positive delta is 0. So if the user enters the 3–5am
  window at 03:00 and again at 04:00, the second time
  `(04:00 − 03:00).days == 0` and the activation is *not* re-logged —
  good. But across DST transitions or after restoration where
  `_last_auto_setback` was persisted in local time, the `.days` math can
  go negative (delta < 0 → `.days == -1`), making `(-1).days > 0` False
  and silently skipping the activation log. Use UTC throughout and
  compare seconds, not `.days`.

- **managers/night_setback_calculator.py:285–289** —
  `recovery_deadline` is parsed with `hour, minute = map(int, deadline.split(":"))`
  with no validation. A misconfigured `"7:00am"` raises `ValueError` at
  runtime, which will only surface in logs, not as an actionable
  config-flow error. Apply at validation time in `climate_setup.py` or
  catch and `_LOGGER.error` with the zone id.

- **central_controller.py:632–656 (`async_cleanup`)** — Cancels all four
  task references under the lock, then awaits them outside the lock.
  Good, but: after cancelling `_heater_startup_task` etc., its `finally`
  block (lines 204–207) will try to `async with self._startup_lock:` — by
  the time it gets the lock, `async_cleanup()` has returned. If
  `async_cleanup()` is followed by deleting the controller reference,
  the task's `finally` block calls into a partially-torn-down object.
  Fix: in `async_cleanup`, after `await task` for all tasks, ensure the
  state fields are not reset out from under another caller, or simply
  set a `_closed` flag that the delayed-startup body checks before
  re-acquiring the lock.

## Medium

- **coordinator.py:147–160 (`get_transport_delay_for_zone`)** — The slug→
  entity-id reconstruction `f"climate.{zone_slug}"` is fragile and
  duplicates state that should live in zone_data. If a zone slug ever
  diverges from `entity_id.split(".")[1]` (e.g. user renames the
  underlying climate entity), transport delay silently returns 0.
  Replace with a direct lookup of `zone_data["climate_entity_id"]`.

- **coordinator.py:434–450 (`get_aggregate_demand`)** — Two full passes
  over `_demand_states` (heat and cool). For a typical small house
  (≤ 20 zones) this is irrelevant; flagged only because the demand
  states are looked up on every state attribute read and from
  CentralController. Trivially: single pass returning a dict.

- **coordinator.py:515–533 (`get_active_zone_setpoints`)** — Performs
  the import inside the function. Move to module top with the others.

- **coordinator.py:265–293 (cooling supply temp/margin)** — Both
  properties build `auto_mode_config = self._config.get(...)` on every
  read. Cache once in `__init__`. Also: `cooling_supply_margin`
  returning `0`/`False` from the dict-`get` will be treated as a falsy
  fallback target — use `is not None` (already done for margin, but the
  `or` chain in `cooling_supply_temp` will swallow a literal `0`,
  which probably shouldn't be a valid supply temp anyway).

- **coordinator.py:43–80 (`__init__`)** — Type annotation on line 64
  (`self._auto_mode_switching: AutoModeSwitchingManager | None = None`)
  is an *assignment*-annotation inside an `else` branch, which Pyright
  flags as a redeclaration of the same name (line 62 sets the same
  attribute without an annotation). Move the annotation to the class
  body or to the first assignment.

- **coordinator.py:699–948 (`ModeSync`)** — Class is bolted on at the
  end of `coordinator.py`, pushing the file to 948 lines. CLAUDE.md
  says "Max file length: 800 lines — extract into modules when
  exceeded." Extract `ModeSync` to `coordinator/mode_sync.py` (or
  similar). Same recommendation for `central_controller.py` at 656
  lines (already approaching the limit; the per-mode duplication is the
  primary contributor and could collapse into a generic `_DeviceManager`).

- **coordinator.py:912 (`ModeSync._set_zone_mode` except branch)** —
  Broad `except Exception` catches and logs without re-raising. This is
  fine for resilience but masks programming errors; consider catching
  `HomeAssistantError, ServiceNotFound` specifically and logging
  unexpected exceptions with `_LOGGER.exception`.

- **managers/auto_mode_switching.py:131–145** — `weather.get_forecasts`
  is called with `blocking=True, return_response=True`. If the weather
  integration's response shape changes (HA breaking changes do
  occasionally rename `forecast` to `forecasts`), this silently returns
  `None`. Add a debug log of the raw result keys for diagnostics.

- **managers/night_setback_calculator.py:114–122 (weather lookup
  fallback list)** — Hard-coded fallback to `weather.home`,
  `weather.knmi_home`, `weather.forecast_home` is brittle and unrelated
  to the user's actual configured weather entity. Once the
  critical-bug fix above (use `coordinator.weather_entity`) is applied,
  delete the fallback list entirely.

- **managers/night_setback_calculator.py:170–191 (`parse_sunset_offset`)** —
  Heuristic "≤12 means hours, >12 means minutes" is surprising and
  un-documented in user-facing docs. Either deprecate the bare-number
  form (require `h` or `m`) or document explicitly. Also raises
  `ValueError` on malformed input.

- **managers/night_setback_calculator.py:282–302** — When `end_time`
  parsing fails the fallback chain (`recovery_deadline` → `07:00`) is
  reasonable, but if `recovery_deadline` is itself malformed the
  `int(...)` calls raise. Wrap in try/except with a clear log.

- **managers/night_setback_manager.py:382–392 (`consume_transition`)** —
  Single-shot read with implicit clear. If two consumers exist, the
  second one never sees the transition. Document the single-consumer
  contract or fan out via the `CycleEventDispatcher`.

- **managers/events.py:189–230 (`CycleEventDispatcher`)** — Listeners
  list is mutated during iteration risk: `emit()` iterates
  `self._listeners[event_type]`; if a callback calls `subscribe` or
  `unsubscribe` for the same event_type during dispatch (e.g. a
  one-shot listener), Python raises `RuntimeError: list changed size
  during iteration` on subsequent emits. Iterate over `.copy()` or use
  a snapshot.

- **managers/events.py:177–181** — `CycleEvent` is a stringified union
  rather than a type alias. With `from __future__ import annotations`
  this still evaluates lazily, but a real `TypeAlias = ...` would help
  IDE/type-checker. Use `from typing import TypeAlias` and a Union.

- **central_controller.py:24–25, 269–311** — `TURN_OFF_DEBOUNCE_SECONDS`
  is a module-level constant (10 s) with no override; this hides
  flickering risk for very large flywheels (district heating). Consider
  exposing as config or scaling with heating type.

- **central_controller.py:78** — `_consecutive_failures` is keyed by
  `entity_id` only, not `(entity_id, service)`. A failing turn-on and a
  succeeding turn-off on the same entity will reset the counter even
  though the turn-on is still failing. Probably acceptable.

- **central_controller.py:497–587 (`_call_switch_service`)** — Catches
  bare `Exception` with retry. `KeyboardInterrupt`/`SystemExit` are not
  `Exception` subclasses, so OK. Re-raising `asyncio.CancelledError`
  would be safer — currently a cancel propagating into this method
  would be caught by the bare `except Exception` block? No — in Python
  3.8+, `CancelledError` inherits from `BaseException`, not
  `Exception`, so it does propagate. OK.

- **coordinator.py:377–432 (`_is_high_solar_gain`)** — Reads
  `zone_data.get("window_orientation")` per zone per call. This is a
  hot-path helper; cache the orientations into a list at zone
  registration. Also: the docstring mentions "elevation > 15 degrees"
  but the threshold is hardcoded — extract to a constant.

## Low / nits

- **coordinator.py:8** — Unused import `datetime` (only `timedelta` is
  used directly; `datetime` is referenced only in type annotations on
  line 377).
- **coordinator.py:16–23** — `try / except ImportError` fallback for
  relative→absolute imports. This pattern is normal for HA tests but
  invisible to mypy/pyright in strict mode. Document why.
- **coordinator.py:521** — `from homeassistant.components.climate import HVACMode`
  is duplicated (already imported at module level on line 13). Drop.
- **coordinator.py:447–450** — Returned dict keys "heating"/"cooling"
  are strings; consider an enum to match `HVACMode` semantics.
- **coordinator.py:53–57** — `_outdoor_temp_unsub: Any = None`
  annotation absent. Use `CALLBACK_TYPE | None`.
- **coordinator.py:64** — Mid-`else` annotation (mentioned above).
- **central_controller.py:65–72** — Task fields lack
  `asyncio.Task[None] | None` parameterization. Minor.
- **central_controller.py:632–656** — `cleanup` typo risk: while iterating
  the four tasks under the lock, a fifth task could be created by a
  concurrent caller. Document that cleanup must be the last action.
- **managers/auto_mode_switching.py:281** — Unnecessary
  `attrs["auto_mode_switching_enabled"] = True` — by definition this
  manager is only instantiated when enabled. Caller already knows.
- **managers/night_setback_manager.py:11–18** — `try/except ImportError`
  with fallback `HomeAssistant = Any` is fragile: any *test* import
  failure now silently changes the type. Prefer a single conditional
  `if TYPE_CHECKING:` import; the `dt_util = None` fallback is unused
  because production code always succeeds.
- **managers/night_setback_manager.py:163–177** — `update_days_at_maintenance_cap`
  increments by 1 per call, but the docstring doesn't specify how often
  it's called; with a 30s coordinator loop you'd be at 7 days in
  ~3.5 min. Confirm this is invoked exactly once per day by the caller.
- **managers/night_setback_calculator.py:124–168** — Magic numbers
  (+60, +30, +15, −30, −45 minutes) buried in code. Extract to module
  constants with comments.
- **managers/night_setback_calculator.py:330** — `_LOGGER.info` per
  cycle on every coordinator tick — moderately noisy. Demote to
  `debug` when state hasn't changed.
- **managers/notification_manager.py:62–65** — Splitting
  `notify_service` on `.` accepts both `"mobile_app_iphone"` and
  `"notify.mobile_app_iphone"` but silently drops the domain prefix.
  Validate at config-flow time.
- **managers/notification_manager.py:74, 91** — Broad `except Exception:`
  with `_LOGGER.exception(...)` is fine; consider also tracking failure
  count like `central_controller` does so a misconfigured notify
  service doesn't spam logs.
- **helpers/registry.py:6–15** — `try/except ImportError: pass` swallows
  the failure silently, then references `er`, `ar`, `fr` later. In a
  testing environment without HA those references will raise
  `NameError`, not `ImportError`. Use a clear shim or skip the
  fallback entirely if tests inject HA.
- **helpers/hvac_mode.py:11–13** — `TYPE_CHECKING` block contains only
  `pass`. Remove the empty block.
- **protocols.py:34–58** — `TemperatureState` exposes `_ext_temp` /
  `_cold_tolerance` (underscore-prefixed) on a public protocol. Protocols
  describing public contracts should not require accessing "private"
  attributes; this leaks implementation details and prevents alternative
  implementations. Refactor to public properties on the protocol while
  keeping the underscore attributes as backing storage on the entity.

## Architectural observations

- The split between `NightSetbackManager` (state) and
  `NightSetbackCalculator` (logic) is good in principle, but the manager
  reaches into `_calculator._get_target_temp()` (lines 249, 295, 356,
  374) — a private method — to read target temp. The calculator should
  expose this publicly, or the manager should hold its own
  `get_target_temp` callback (it already has access to one because the
  calculator was constructed with it).

- `ModeSync` and `CentralController` both maintain their own state
  about zones and rely on coordinator-owned dicts, but neither is
  notified on zone *unregistration* in a structured way. Consider a
  coordinator-level pub/sub (use the existing `CycleEventDispatcher`
  with new event types `ZoneRegisteredEvent` / `ZoneUnregisteredEvent`)
  so all consumers reliably see lifecycle events.

- `AutoModeSwitchingManager.async_evaluate` mixes three responsibilities:
  rate-limiting, season classification, mode decision, and state
  bookkeeping. Splitting into `_compute_target_mode()` (pure) +
  `_should_switch()` (rate-limit) + `_record_switch()` would make
  testing the threshold logic against fixtures dramatically easier and
  resolve the High-severity "_last_switch updated on no-op" issue.

- `CentralController` duplicates heater/cooler logic almost verbatim
  (5 pairs of nearly identical functions). A `_DeviceController(name,
  switches)` helper class would cut the file by ~40% and eliminate
  copy-paste drift (which already exists — e.g. `_update_heater` has
  slightly different comment wording than `_update_cooler`).

- `coordinator.py` is doing too much: zone registry, EMA filter,
  solar-gain helper, mode-sync, auto-mode dispatch, manifold registry
  facade, sun position helper, central-controller wiring. Several of
  these (sun, solar gain, manifold facade) deserve their own modules.

- `NotificationManager` is intentionally simple but lives in
  `managers/` while doing nothing manager-like (no state machine, no
  protocol dependency). Consider relocating to `helpers/notifications.py`.

- The coordinator unconditionally returns
  `{"zones": self._zones, ...}` from `_async_update_data` — i.e. shares
  the **live mutable dict** with all consumers. A consumer mutating
  this dict (defensively or by mistake) corrupts coordinator state.
  Either return a deep copy or document immutability via
  `MappingProxyType`.

## Positive observations

- The single-flight guard pattern in `update_zone_demand` and the
  rerun-aware debounce in `_delayed_*_turnoff` show real concurrency
  thinking; the issues called out above are refinements rather than
  fundamental design problems.
- `ModeSync._sync_in_progress` correctly prevents the intra-ModeSync
  feedback loop (the cross-component loop with `_apply_house_mode` is
  the only remaining gap).
- The `CycleEventDispatcher` is a clean pub/sub abstraction and is the
  right primitive to lean on for the zone-lifecycle events suggested
  above.
- `central_controller._call_switch_service` has thoughtful error
  handling: distinguishes `ServiceNotFound` (no retry) from
  `HomeAssistantError` (retry with backoff), tracks consecutive
  failures, and logs at the right levels.
- The protocol-based decomposition (`TemperatureState`, `PIDState`,
  `HVACState`) is a great pattern and properly applied in many
  managers.
- Night-setback graduated-delta logic (lines 292–353 of
  `night_setback_manager.py`) correctly handles three regimes
  (suppressed / capped / full) and toggles state-tracking flags to
  avoid log spam.
- `AutoModeSwitchingManager` correctly falls back to current outdoor
  temp when forecast is unavailable, and applies hysteresis before
  the season-lock check — good ordering.
- Type annotations broadly follow PEP 604 (`X | None`) — only a few
  laggards (`_outdoor_temp_unsub`, `Any` on `_thermal_group_manager`).
