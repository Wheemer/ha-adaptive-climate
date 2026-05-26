# Heater Actuation & Cycle Tracking Review

Scope: `managers/heater_controller.py`, `managers/pwm_controller.py`, `managers/cycle_tracker.py`, `managers/cycle_metrics.py`, `managers/temperature_manager.py`, `managers/heat_pipeline.py`, `protocols.py`.

## Critical (must fix)

- **managers/heat_pipeline.py:1-82 and managers/heater_controller.py:179-186** — Dead code. `HeatPipeline` is instantiated and stored on `HeaterController._heat_pipeline`, but `valve_opened()`, `valve_closed()`, `committed_heat_remaining()` and `calculate_valve_open_duration()` are never called anywhere in the component (verified with grep across the full tree). CLAUDE.md documents an active "Committed heat tracking" feature that "tracks in-flight heat and subtracts from next cycle's duty calculation. Learning splits overshoot into controllable vs committed portions." The implementation is missing — `pwm_controller.calculate_adjusted_on_time` simply adds `transport_delay + valve_actuation_time` to the on-time and never consults a pipeline. Either wire the pipeline through `PWMController.async_pwm_switch` (call `valve_opened/closed` from `HeaterController.async_turn_on/off`, query `committed_heat_remaining` in `calculate_valve_open_duration`) or delete the module + docs section. The current state is the worst of both worlds: docs lie, code is unreachable.

- **managers/heater_controller.py:553-567** — `is_active()` for valve devices crashes on a missing entity and aborts the entire loop. `self._hass.states.get(entity).state` raises `AttributeError` when `states.get()` returns `None`; the `except AttributeError` is *outside* the `for` loop, so a single unavailable entity makes the method return `False` and silently skip every other entity in the list (e.g., a multi-valve manifold). Replace with per-entity null guard:
  ```python
  for entity in entities:
      state_obj = self._hass.states.get(entity)
      if state_obj is None or state_obj.state in ("unknown", "unavailable"):
          continue
      ...
  ```
  Also handles `STATE_UNAVAILABLE`/`STATE_UNKNOWN`, which currently get `float("unknown")` → `ValueError` → falls through to the `in ["on","open"]` branch returning `False`.

- **managers/heater_controller.py:843-949 (`async_set_valve_value`)** — State machine stuck in valve mode. SETTLING_STARTED in valve mode is emitted only at lines 897-909 when `value < 5.0` **AND** `abs(current_temp − target_temp) <= 0.5`. If the valve closes from 5%→0% while temperature is far from target (e.g. window opened, contact handler skipped, mode change), `_cycle_active` stays `True` indefinitely. Subsequent re-openings hit the `if new_active and not self._cycle_active` guard at line 921, so no new `CYCLE_STARTED` is emitted, and the upstream `CycleTrackerManager` stays in `HEATING`/`COOLING` forever — its settling timeout never fires either because it depends on a `SETTLING_STARTED` event to enter `SETTLING`. The valve path needs the same demand-zero debounce / unconditional emission the PWM path has in `async_set_control_value` (see line 992).

- **managers/cycle_metrics.py:421** — `calculate_undershoot` is called with the **raw** `temperature_history`, which starts at the cold pre-cycle temperature. For any cycle that begins below setpoint (every recovery cycle, every fresh demand), undershoot equals `target − start_temp` even when the system later reached and held the target perfectly. This metric feeds `UndershootDetector` and the convergence trio (`inter_cycle_drift`, `settling_mae`, `undershoot`) referenced in CLAUDE.md. Symptoms: floor_hydronic recovery cycles will reliably report undershoot ≥ 0.4°C → consecutive-failure counter ramps Ki on cold mornings even though control is fine. Use the dead-time-filtered history or restrict to samples after `_device_off_time`/`get_settling_start_time()`:
  ```python
  settling_start = self.get_settling_start_time()
  settling_history = [(t, v) for t, v in temperature_history if settling_start is None or t >= settling_start]
  undershoot = calculate_undershoot(settling_history or temperature_history, target_temp)
  ```

- **managers/cycle_metrics.py:433-441** — `heater_active_periods` for the disturbance detector is fabricated by setting `heating_end = temperature_history[len // 2][0]` (the median sample timestamp). The recorder already owns the real values: `self._device_on_time` and `self._device_off_time` from `HEATING_STARTED`/`HEATING_ENDED` events. The current heuristic is meaningless and will mislabel cycle-internal heating periods, polluting disturbance detection. Replace with:
  ```python
  heater_active_periods = []
  if self._device_on_time is not None:
      end = self._device_off_time or temperature_history[-1][0]
      heater_active_periods.append((self._device_on_time, end))
  ```

## High

- **managers/heater_controller.py:1132 lines total** — Violates CLAUDE.md "Max file length: 800 lines - extract into modules when exceeded". Split candidates: timer/debounce logic (`_emit_settling_started_*`, `cancel_pending_timers`), service-call wrapper (`_async_call_heater_service`, `_get_number_entity_domain`), and the cycle-counting/cycle-active bookkeeping each form coherent modules.

- **managers/heater_controller.py:1045** — `if abs(control_output) == self._difference:` is float-equality on a PID output. Even with `_output_precision` rounding upstream the result depends on float arithmetic (`difference` is `output_max - output_min`, possibly `100.0 - 0.0` so usually exact, but vulnerable to any future config supplying floats). Use `abs(control_output) >= self._difference - 1e-6` or `math.isclose(...)`.

- **managers/heater_controller.py:704** — `time.monotonic() - get_cycle_start_time() >= self._min_closed_time` reads `min_closed_time` but the comparison is against the *previous* cycle's *start* time (per `set_last_heat_cycle_time` usage). Semantically `get_cycle_start_time` is the time the device last changed state; the variable name is misleading. Worse, this check gates turn-on without considering the symmetric `effective_min_open_time` for valve actuators — short-pulse protection is asymmetric. Document or rename + consider valve-actuation symmetry.

- **managers/heater_controller.py:725-729, 805-811, 1002-1006, 1033-1037** — `async_call_later` is invoked with a `lambda` that captures `hvac_mode` and `was_clamped` by closure at scheduling time. If the user changes mode (HEAT↔COOL↔OFF) during the 2×PWM debounce, the deferred `SETTLING_STARTED`/`HEATING_*` event is emitted with the **stale** mode and the cycle tracker may dispatch it to the wrong handler or reject it (see `_on_settling_started` line 403). At minimum the lambda should re-read the live mode from a callback; ideally `cancel_pending_timers()` should be called from the climate entity's `async_set_hvac_mode` path (only `force=True` `async_turn_off` cancels them today).

- **managers/heater_controller.py:160-161 and climate.py (state restore)** — `_cycle_active` and `_has_demand` are reset to `False` on every `__init__` and never restored from `RestoreEntity` state. After an HA restart while the heater is physically ON and the cycle was previously in HEATING, the first control tick goes:
  1. `async_set_control_value` sets `_has_demand=True` (line 989)
  2. `async_pwm_switch` routes to `heater_controller.async_turn_on`
  3. `is_active=True` so line 698 hits the "restart case" branch and emits `CYCLE_STARTED`
  4. `CycleTrackerManager._on_cycle_started` calls `_metrics_recorder.reset_cycle_metrics()` (line 362) wiping any restored device-on/off timestamps and clamping state for the *in-progress* cycle.
  
  Net effect: every HA restart in the middle of a cycle discards that cycle's clamp/integral observations and starts metrics from scratch with cycle_start_time = now (not the original start). At minimum, document this and skip the in-progress cycle for learning (currently the next SETTLING_STARTED will record a metrics row spanning only the post-restart slice). Better: persist `cycle_active` + `cycle_start_time` and rebuild minimal state.

- **managers/pwm_controller.py:341** — `heater_controller._has_demand = True` reaches across the API boundary into a private attribute from a different module. PWMController is supposed to be a delegate. Add a public setter on `HeaterController` (`mark_pulse_demand()`) and call that.

- **managers/cycle_tracker.py:121** — `deque(maxlen=2000)` silently drops the oldest samples once exceeded. At 30s sample interval (typical) that's 16h; with restart-day floor_hydronic settling timeouts up to 4 hours plus rich preheat sampling this is fine, but a sub-30s sensor or settling window of `SETTLING_TIMEOUT_MAX = 240` minutes at 5s sampling = 2880 samples → silent truncation that corrupts `inter_cycle_drift` / `settling_mae` because `temperature_history[0]` is no longer the cycle start. Either raise the cap or guard `start_temp = temperature_history[0][1]` against deque rollover (e.g., capture `_cycle_start_temp` once at `_on_cycle_started`).

- **managers/cycle_tracker.py:121-122** — `_temperature_history` is a `deque[tuple[datetime, float]]` but `_outdoor_temp_history` is a plain `list` with no cap. On a 4-hour settling window the outdoor list grows unbounded — minor memory but unbounded growth in a long-running HA process is worth fixing for parity.

- **managers/cycle_tracker.py:128-144** — Heating-type-aware settling timeout is wired but never used: constructor takes `heating_type` and `HEATING_TYPE_CHARACTERISTICS[ht]["max_settling_time"]` exists in `const.py:239` (90 / 60 / 30 / 20 min), yet `_max_settling_time_minutes` is derived only from `thermal_time_constant` or a generic 120-min default. Floor systems with a missing `area_m2` (no tau computed) fall back to 120 min — too short for hydronic. Use the table when `settling_timeout_minutes` and `thermal_time_constant` are both `None`.

## Medium

- **managers/cycle_tracker.py:354-359** — `_on_cycle_started` compares `event.hvac_mode == "heat"`. Events are typed `hvac_mode: str` (events.py:37) but `HeaterController` emits `HVACMode.HEAT` (the StrEnum). Currently works because `HVACMode` is a HA `StrEnum`, but the typing claim is wrong. Either type the events as `HVACMode | str` and compare via the enum, or normalize at emit time (`hvac_mode=str(hvac_mode)`).

- **managers/cycle_metrics.py:480-490** — Mode inference re-reads `self._get_hvac_mode()` at finalization time rather than the mode of the cycle. If the user flipped mode after `SETTLING_STARTED`, `mode` is wrong. Should be captured at `_on_cycle_started` and threaded through `record_cycle_metrics`.

- **managers/cycle_metrics.py:467-468** — `inter_cycle_drift = start_temp - self._prev_cycle_end_temp` is computed only when the previous cycle finalized successfully. Any aborted cycle (contact_sensor, setpoint_major) skips `record_cycle_metrics` entirely, so the *next* cycle compares against the cycle-before-last — false drift signal. Either reset `_prev_cycle_end_temp` on abort or store a timestamp and discard if stale (> 2h).

- **managers/heater_controller.py:295-309** — `_emit_heating_started_delayed` ignores `_cycle_active`. If the user changed mode or aborted between scheduling and firing, the event still fires with stale mode (see High note above). Mirror the `if self._cycle_active` guard used in `_emit_settling_started_debounced`.

- **managers/pwm_controller.py:148-181** — `calculate_adjusted_on_time` adds `transport_delay + valve_actuation_time` to every on-time. But the comparison check that decides if the heater should turn off (`pwm_controller.py:410`: `time_to_close <= time_passed`) compares `time_to_close = time_on - close_command_offset` where `close_command_offset = valve_actuation_time / 2`. So we keep the valve open for `transport_delay + valve_actuation_time + max(heat, min_open)` then subtract `valve_actuation_time/2` to early-close. Net open = `transport_delay + valve_actuation_time/2 + max(heat, min_open)`. For floor_hydronic (transport ≈ pipe-fill-time, valve=120s) the half-valve subtraction is correct, but no symmetric `transport_delay/2` cancels the delay added at the top — so the cycle overruns by approximately one full transport_delay every burst. This matches the "overshoots after manifold warms up" symptom typical of hydronic systems. Verify intent.

- **managers/pwm_controller.py:233-237** — `no_demand` check uses `hvac_mode == HVACMode.HEAT` but the comparison is performed only after the heat-mode sign convention is assumed. In COOL mode with PID inverted, `abs(control_output)` is used in `calculate_adjusted_on_time` (line 254) and `_calculate_heat_duration` (line 261) — sign is stripped. The fact that line 234 also short-circuits on `control_output == 0` and the COOL branch on line 236 catches `> 0` is correct *in heat mode logic*, but the test reads the sign of `control_output` differently than the magnitude logic below. Add a unit test or comment confirming `control_output` polarity convention for COOL mode (it appears the rest of the file always treats positive as demand in both modes — clarify).

- **managers/cycle_metrics.py:319-347** — `_schedule_learning_save` reaches into `self._hass.data.get(DOMAIN, {}).get("learning_store")` on every cycle. CLAUDE.md mandates using `self._coordinator` cached property and bans inline `hass.data.get(DOMAIN, {}).get("coordinator")` lookups — same anti-pattern. Inject `learning_store` (or a `LearningStoreProtocol`) into the constructor.

- **managers/cycle_tracker.py:583-599** — Settling timeout uses `async_call_later(... minutes*60, _settling_timeout)`. The cancel handle is stored in `_settling_timeout_handle`. If two `SETTLING_STARTED` events fire back-to-back (PWM low-output timer + demand-zero timer racing — both can fire because mutual exclusion only happens *inside* the handlers after one fires), `_schedule_settling_timeout` cancels-then-rescheduules — fine. But if `_on_cycle_started` follows a `SETTLING_STARTED` without explicit timeout cancel, the old timer keeps running and may finalize a brand-new cycle midway. `_reset_cycle_state` does call `_cancel_settling_timeout` but only on abort; `_on_cycle_started` itself doesn't cancel. Add `self._cancel_settling_timeout()` in `_on_cycle_started` line 380.

- **managers/heater_controller.py:1027-1042** — Low-output timer creation requires `self._low_output_timer is None and self._demand_zero_timer is None`. If demand drops 0 → small positive → 0 (typical PID dither), the demand-zero timer fires at line 992 cancelling the low-output timer, but the next "0 → small" can leave both timers null with a stalled cycle if logic ordering is unlucky. The reset paths are inside both fire callbacks (lines 216-218, 240-242), so this is consistent — but the asymmetric "demand-zero takes precedence" rule should be documented in a comment because it determines learning-cycle boundaries.

- **managers/heater_controller.py:43-63** — The HA-import fallback (`HAS_HOMEASSISTANT`) silently substitutes string sentinels. If imports partially fail (e.g., new HA version removed `ATTR_BRIGHTNESS_PCT`), `ImportError` is caught for the entire block and the module limps along with incorrect string constants — service calls then send `position=...` to lights, etc. Either narrow the try/except to only the symbols actually optional in tests or remove the fallback (tests should mock HA properly).

- **managers/cycle_tracker.py:443-454** — `_on_contact_pause` ignores `event.entity_id` from the event payload — the reason string is hardcoded "contact sensor pause (window/door opened)". Including the entity makes debugging multi-sensor zones much easier.

- **managers/temperature_manager.py:243-247** — `if temperature in self._preset_temp_modes` does dict lookup on a float key, which is fragile (`20.0 == 20.0` but `19.99999 in {19.99999: ...}` only if same precision was stored). Safer: iterate and use `math.isclose` with a 0.05°C tolerance.

- **managers/temperature_manager.py:299-333** — `async_set_preset_temp` has stringly-typed kwargs with magic substrings (`"disable" in preset_name`). A preset called `comfort_temp_disable` works but `comfort_temp` with disable-flag arg doesn't compose. Define an enum or dedicated method per preset.

## Low

- **managers/heater_controller.py:7** — `from typing import ... Callable` — Python 3.9+ uses `collections.abc.Callable`. Project targets HA which is 3.11+; not blocking but inconsistent with PEP-604 mandate in CLAUDE.md.

- **managers/heater_controller.py:188-204** — `_get_pid_was_clamped` / `_reset_pid_clamp_state` are passthroughs to optional callbacks. Mark them `@staticmethod`-style with early return or inline at call sites; current indirection adds no value.

- **managers/heater_controller.py:485-503** — `_increment_cycle_count` has a confusing signature: `is_now_off` is in the name and arg, but inside the function it inverts to derive `_last_*_state = not is_now_off`. Either drop `is_now_off` (always called with `True`) or rename.

- **managers/heater_controller.py:309, 325** — `self._valve_open_timer = None` / `self._valve_close_timer = None` are assigned *inside* the `_emit_*_delayed` callbacks. If `cancel_pending_timers()` was called *before* the callback fires (already cancels), the timer handle was already cleared — assignment is redundant but harmless.

- **managers/pwm_controller.py:398-401** — `time_on *= self._min_closed_time / time_off` mutates `time_on` to enforce a minimum off-time. The arithmetic is correct only because Python uses true division; with integer `_pwm` and edge cases the resulting `time_on` may exceed `_pwm`. Add `time_on = min(time_on, self._pwm - self._min_closed_time)` to bound it.

- **managers/cycle_metrics.py:215-249** — `_calculate_mad` recomputes the median twice (once for raw values, once for deviations); statistics module's `statistics.median` would be clearer. Trivial.

- **managers/cycle_tracker.py:96-102, 449, 472, 505, 577, 735** — Local imports inside methods (`from ..const import ...`, `from ..adaptive.cycle_analysis import ...`). Done to break circular imports, but six different lazy import sites is excessive — consolidate at module top with `TYPE_CHECKING` guards where needed.

- **managers/cycle_metrics.py:484-490** — `if hvac_mode == "heat"` etc. — same StrEnum stringification ambiguity as cycle_tracker. Use `HVACMode.HEAT`.

- **managers/heater_controller.py:1132 + cycle_tracker.py:790** — Both files have generous logging at `info` level inside the per-tick hot path (`_LOGGER.info("Refresh state ON ...")`). HA users with many zones will see hundreds of log lines per minute. Demote to `debug` for the non-state-change branches.

- **managers/cycle_metrics.py:550-551** — `self._hass.async_create_task(self._on_auto_apply_check())` after `record_cycle_metrics` runs without holding any reference to the task. `async_create_task` returns the task; if `auto_apply_check` raises, the exception is logged but the task may be lost during shutdown. Use `hass.async_create_background_task(coro, "adaptive_climate_auto_apply")` (HA 2024+) for proper lifecycle.

- **managers/heater_controller.py:583-590** — `self._hass.bus.async_fire(f"{DOMAIN}_heater_control_failed", ...)`. Event name is a runtime f-string with no `EVENT_*` constant — easy to typo in a listener. Define `EVENT_HEATER_CONTROL_FAILED = f"{DOMAIN}_heater_control_failed"` in `const.py`.

- **managers/heat_pipeline.py:51** — `min(time_open, self.transport_delay)` clamps the in-flight estimate to `transport_delay`. If `valve_time > transport_delay` (rare, but configurable), the model under-reports heat. Document the invariant `valve_time <= transport_delay` or compute properly.

## Architectural observations

- **Cycle-event coupling is bidirectional**: `HeaterController` *emits* events while *also* checking `_cycle_active` to decide whether to emit. `CycleTrackerManager` *also* tracks state via its own `_state` machine. There are effectively two independent state machines for one logical cycle, kept in sync only by event ordering. Race-prone — consider making `CycleTrackerManager` the sole owner of "is a cycle active?" and having `HeaterController` query it.

- **`HeaterController` violates Manager-Protocol convention from CLAUDE.md**: it receives a concrete `AdaptiveThermostat` reference, then uses `getattr(self._thermostat, "_current_temp", 0.0)` (lines 285, 292, 899) to read state. This is exactly what `ThermostatState` Protocol was created to fix. Accept a `ThermostatState` (or a narrower subset like `TemperatureState`) instead. As a bonus, the silent default `0.0` would become a typed `float | None`.

- **Cross-module private access**: `pwm_controller.py:341` writes `heater_controller._has_demand`; `cycle_tracker.py:237-272` exposes `_interruption_history`, `_was_clamped`, `_device_on_time`, `_device_off_time`, `_integral_at_tolerance_entry`, `_integral_at_setpoint_cross`, `_transport_delay_minutes` properties solely "for testing". Better split: a public read-only `CycleMetricsView` for tests and a private mutation API guarded by the manager.

- **`PWMController` is owned by `HeaterController` but takes `thermostat` directly**: redundant coupling. Pass only what's read (`entity_id` for logging, optional `_current_temp/_target_temp` callbacks for the "skip pulse" safety check at pwm_controller.py:292-332).

- **`HeatPipeline` design assumes uniform delivery**: `committed_heat_remaining` linearly interpolates from valve_open to valve_closed+transport_delay. Real hydronic systems have temperature ramp-up and ramp-down profiles. If this is to be used, model it as exponential rise/decay matched to thermal mass, not a step function. Worth deciding before wiring it.

- **No restart-safety for `PWMController`**: `_duty_accumulator_seconds` is persisted via `set_duty_accumulator`/`reset_duty_accumulator` and restored from RestoreEntity, but `_last_accumulator_calc_time` is reset to `None`. After restart, the first tick will set baseline (no accumulation) — that's correct, but worth a comment because the accumulator delta calc uses monotonic time which is process-relative.

## Positive observations

- `cancel_pending_timers()` (heater_controller.py:253-266) cleanly tears down all four async timers — good shutdown hygiene.
- `CycleMetricsRecorder` is well-decomposed from `CycleTrackerManager` (single responsibility).
- `_finalizing` guard (cycle_tracker.py:585-588, 629-633) properly prevents reentrant finalization from racing timer + temperature-update paths.
- Service-call error handling in `_async_call_heater_service` is exemplary: distinguishes `ServiceNotFound` from `HomeAssistantError`, fires a domain event on failure, clears state on success.
- `HVACMode`-aware turn-off enforces `effective_min_open_time` for compressor protection (heater_controller.py:787-833) — good compressor lifespan guarding.
- `dt_util.utcnow()` and `time.monotonic()` are used correctly throughout — no `datetime.now()` or `time.time()` violations in scope.
- No `assert` statements in production code in scope. PEP-604 `X | None` is used consistently.
- `@callback` decorators are correctly applied only to synchronous methods.
