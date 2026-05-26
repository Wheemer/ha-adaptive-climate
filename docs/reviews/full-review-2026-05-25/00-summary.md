# Full Codebase Review — 2026-05-25

Scope: every Python file under `custom_components/adaptive_climate/` (~40 kLOC, 50+ modules), split into six parallel review streams. Detailed findings live in `01-` through `06-`.

| # | Stream | File | Critical | High |
|---|--------|------|----------|------|
| 1 | Climate orchestration | `01-climate-orchestration.md` | 5 | 13 |
| 2 | PID & control output | `02-pid-control.md` | 5 | 11 |
| 3 | Heater actuation & cycles | `03-heater-cycle.md` | 5 | 8 |
| 4 | Adaptive learning | `04-adaptive-learning.md` | 10 | 15 |
| 5 | Multi-zone coordination | `05-multi-zone.md` | 7 | 11 |
| 6 | Sensors / services / state attrs | `06-sensors-services.md` | 7 | 12 |
| | **Total** | | **39** | **70** |

---

## Top 12 critical issues (ship-stoppers)

Ranked by user impact × likelihood × difficulty-to-detect. Each links to the originating review for full context and fix.

1. **PID uses wall-clock `time()` for dt** — `pid_controller/__init__.py:5,514,532,537`. NTP step or DST jump injects multi-hour `dt` straight into Ki, causing massive windup. Trivial swap to `time.monotonic()`. [02]
2. **Mode-confused auto-apply counter** — `pid_tuning.py:324` always increments the heating counter regardless of active mode. Cooling never advances past "first apply" gate; heating budget silently consumed by cooling activity. [04]
3. **Destructive learning-data migration** — `learner_serialization.py:216` wipes everything if `format_version != 10`. Code comments claim v7→v10 migrations exist; none do. Every storage-version bump destroys all user learning. [04]
4. **`_heating_cycle_count` never persisted** — `confidence.py` increments it but it's missing from `learner_to_dict`. After every HA restart, learning status reverts to "collecting" until cycles re-accumulate; auto-apply blocked. [04]
5. **`HeatPipeline` is dead code** — `heat_pipeline.py` instantiated but never called. CLAUDE.md documents an active "committed heat tracking" feature; the implementation simply isn't wired up. Either wire it or delete the module + docs. [03]
6. **Bogus undershoot on every recovery cycle** — `cycle_metrics.py:421` passes raw pre-cycle history to `calculate_undershoot`, so undershoot = (target − cold start temp) always. Feeds the undershoot detector → falsely ramps Ki on every cold morning. [03]
7. **Valve state machine can hang** — `heater_controller.py:843-949`. SETTLING_STARTED emitted only when temp within 0.5°C of target; valve closing far from target leaves `_cycle_active=True` forever, breaking all downstream cycle tracking. [03]
8. **`async_set_hvac_mode` is not lock-protected** — `climate.py:1102`. Awaits `_async_heater_turn_off` *before* mutating `_hvac_mode`; a control-loop tick during the await re-enables the heater after user requested OFF. Same race in `async_set_temperature`, `set_preset_mode`, `clear_integral`. [01]
9. **Coordinator listener leak across reloads** — `coordinator.py` schedules listeners + timers in `__init__`; `async_cleanup()` exists but is never wired into `async_unload_entry`. Every reload doubles the subscriptions. [05]
10. **`night_setback_calculator` weather lookup is broken for all non-default entities** — `night_setback_calculator.py:112` reaches into `coordinator._weather_entity` (attribute doesn't exist; coordinator exposes `weather_entity` property). Dynamic recovery-end-time silently falls back to hard-coded list. [05]
11. **Solar gain corrupted in Southern Hemisphere** — `solar/solar_gain.py:109` uses calendar-fixed seasons. Australian/Brazilian/NZ/ZA users get inverted seasons; their summer is labeled WINTER and the seasonal-intensity table silently destroys learning. [06]
12. **`validation.check_auto_apply_limits` will TypeError as soon as pid_history is wired** — `validation.py:182` compares ISO string timestamps to a datetime. Currently masked because callers pass `[]`; the seasonal MAX_AUTO_APPLIES gate is therefore a no-op today, and the moment someone fixes the wiring the auto-apply path crashes. [04]

---

## Cross-cutting themes

### A. Time handling is inconsistent and incorrect in several places
- Wall-clock `time()` in PID (#1).
- `datetime.now()` in `notification_manager.py:96,105` (DST-unsafe). [05]
- `time.monotonic()` floats serialized to persistent storage and either ignored or compared meaninglessly on restore: `KeManager._steady_state_start` [02 #25], `UndershootDetector.last_adjustment_time` [04 critical].
- EMA filter resets on `dt=0` and uses Euler discretization that's unstable for irregular sampling. [05]

Pick one source per use case and apply it everywhere: `time.monotonic()` for in-process elapsed durations, `dt_util.utcnow()` for anything that crosses persistence boundaries or compares across restarts. Stop persisting monotonic floats.

### B. Documentation/code drift (CLAUDE.md is partly fiction)
- `MAX_UNDERSHOOT_KI_MULTIPLIER = 3.0` in code; CLAUDE.md says 2.0. [04]
- `OpenWindowDetector` module is documented in CLAUDE.md but **does not exist** in the tree. [04]
- "Committed heat tracking" is documented as active; `HeatPipeline` is unreachable. [03]
- "Persistence v10 with backward compat"; no migrations implemented. [04]
- Debug-only preheat/humidity attributes documented as nested under `debug.*`; code writes them flat regardless of debug flag. [06]
- `SERVICE_RUN_LEARNING` / `SERVICE_PID_RECOMMENDATIONS` only registered in debug but advertised in `services.yaml`. [06]

Audit CLAUDE.md against actual code in a dedicated pass. Either bring code into line or update docs — the current state misleads contributors and reviewers.

### C. Mode-awareness is partial and inconsistent
- Auto-apply count increments heating regardless of active mode (#2).
- `PIDGainsManager.restore_from_state` only restores HEAT — cooling gains silently dropped on every restart. [02 #4]
- `UndershootDetector` is heating-only (`learning.py:1418` early-returns for COOL).
- `HeatingRateLearner` has no mode separation.
- `ConfidenceTracker._heating_rate_contribution` is mode-less.
- `learning_gate.get_cycle_count()` defaults to HEAT — cooling-only zones never gate on cooling cycles.

Audit every learner/manager for "is this state per-mode?" and make it explicit (or one-mode-only with a clear assert at module boundary).

### D. File length and god-class proliferation
| File | Lines | Limit |
|------|-------|-------|
| `climate.py` | 1938 | 800 |
| `adaptive/learning.py` | 1701 | 800 |
| `managers/heater_controller.py` | 1132 | 800 |
| `coordinator.py` | 948 | 800 |
| `managers/state_attributes.py` | 813 | 800 |
| `managers/cycle_tracker.py` | 790 | 800 (close) |
| `pid_controller/__init__.py` | 724 | OK but dense |
| `central_controller.py` | 656 | 800 (heater/cooler duplication) |

The `*Mixin` split for the climate entity moves code without solving the cohesion problem. `AdaptiveLearner` and `AdaptiveThermostat` are both god classes with 30+ methods and pervasive private-attribute reach-through across module boundaries.

### E. `ThermostatState` Protocol is vestigial
CLAUDE.md mandates "managers receive a `ThermostatState` Protocol, not raw callbacks or thermostat references." In practice:
- `HeaterController` takes a concrete `AdaptiveThermostat` and uses `getattr(self._thermostat, "_current_temp", 0.0)`. [03]
- `KeManager` maintains parallel Protocol-based and callback-based paths in violation. [02 #23]
- `pid_tuning.py` does `getattr(self._state, "_ke_controller", ...)` — not on the Protocol. [02 #28]
- `climate_control.py` reaches into `adaptive_learner._heating_rate_learner._active_session` etc. [01]
- Examples list goes on across every stream.

Either commit to the Protocol (every cross-module access goes through a typed interface) or remove the indirection. Half-measure is worse than either extreme.

### F. Restoration is fragile and lossy across the integration
- `_cycle_active`/`_has_demand` not restored; in-progress cycles are wiped. [03]
- `_heating_cycle_count` not persisted (#4).
- Cooling gains dropped on restore (#C).
- Monotonic timestamps persisted then ignored or compared meaninglessly (#A).
- Restored integral not clamped against (possibly changed) output bounds; first `dt=0` calc skips the clamp. [02 #5]
- `format_version` migration is destructive (#3).
- `auto_learning_setback` piggybacks on regular night-period transition signal, granting a learning-grace twice a day to users who never opted in. [05]

Audit "what survives an HA restart" once and make it uniform. Decide per-field: persisted in UTC ISO, or reset on restart with a documented reason.

### G. Concurrency and lifecycle gaps
- `async_set_hvac_mode` race (#8).
- Coordinator listener leak (#9).
- `central_controller._cancel_*_unlocked` releases lock mid-method (#5-7 in stream 5).
- `update_zone_demand` single-flight drops changes mid-task. [05]
- `_apply_house_mode` doesn't set `ModeSync._sync_in_progress` → O(N²) fan-out. [05]
- `CycleEventDispatcher.emit` iterates listeners without snapshotting; subscribe/unsubscribe during dispatch can `RuntimeError`. [05]
- `async_call_later` callbacks in heater controller capture stale `hvac_mode` if user changes mode mid-debounce. [03]

### H. Inputs to "safety" gates are not validated
- `set_pid_param` and `set_gains` accept NaN/Inf/negative silently. [02 #8,9]
- `decay_integral` / `scale_integral` accept any factor including negative (inverts integral). [02 #10]
- `set_hvac_mode("unavailable")` not validated by state_restorer. [06]
- `recovery_deadline` malformed → `ValueError` deep in calculator. [05]
- Cost-entity currency parsed at runtime into something HA rejects for MONETARY device_class. [06]

NaN entering a PID poisons the whole controller; validate at every public entry point.

---

## Suggested remediation order

Phase 1 — **stop the bleeding** (1-3 days, mostly mechanical):
1. Swap `time()` → `time.monotonic()` in PID. (#1)
2. Wire `coordinator.async_cleanup()` into `async_unload_entry`. (#9)
3. Lock `async_set_hvac_mode` (and friends) or reorder mode-then-actuator. (#8)
4. Fix `night_setback_calculator` to use the `weather_entity` property. (#10)
5. Add NaN/Inf/negative validation in `set_pid_param` and `PIDGainsManager.set_gains`. (#H)
6. Drop solar-gain seasonal calendar in favor of solar-elevation-driven classification, or accept a hemisphere config. (#11)
7. Fix `validation.check_auto_apply_limits` ISO-string parsing and re-wire real `pid_history`. (#12)
8. Persist `_heating_cycle_count` / `_cooling_cycle_count` (or derive from history). (#4)

Phase 2 — **fix learning correctness** (1-2 weeks):
9. Use settling-window-only history in `calculate_undershoot`. (#6)
10. Wire `confidence_tracker.increment_auto_apply_count(mode)` from `pid_tuning.py`. (#2)
11. Make `learner_serialization` non-destructive on unknown versions; implement actual migrations or freeze the schema. (#3)
12. Fix `HeatPipeline` (wire or delete) and resolve the CLAUDE.md drift on Ki cap + Open-Window detection. (#5, #B)
13. Repair valve-mode SETTLING_STARTED emission and add settling-timeout cancel in `_on_cycle_started`. (#7)

Phase 3 — **structural cleanup** (multi-PR, weeks):
14. Split god files: `climate.py`, `learning.py`, `heater_controller.py`, `coordinator.py`, `state_attributes.py`.
15. Commit to `ThermostatState` Protocol — eliminate every `self._*` cross-module reach-through.
16. Centralize integral mutations (analog to `PIDGainsManager`) so the clamp invariant is always enforced.
17. Collapse heater/cooler duplication in `central_controller.py` into a generic `_DeviceController`.
18. Unify the three duplicate `is_paused` implementations into one `PauseDetector`. [06]
19. Audit restoration uniformly — one matrix of "what's persisted, in what unit, how migrated".

Phase 4 — **observability and docs**:
20. Reconcile CLAUDE.md vs code (#B). Generate from code where possible.
21. Add unit tests for: PID NaN injection, learner_serialization round-trip across versions, cycle metrics with settling-only history, multi-zone mode propagation, solar gain in southern hemisphere, weekly snapshot week-numbering.

---

## What's already good

Worth keeping and replicating:
- `dt_util.utcnow()` and `time.monotonic()` are used correctly throughout the heater layer and most of sensors. No `assert` in production, PEP-604 `X | None` consistent, `@callback` only on sync funcs — CLAUDE.md style is largely followed.
- `_call_switch_service` error handling (retry vs no-retry, backoff). [05]
- `cancel_pending_timers` and `_finalizing` reentrancy guards in heater + cycle tracker. [03]
- `build_overrides` priority ordering matches CLAUDE.md schema exactly. [06]
- Single-flight + debounce pattern in `CentralController` and `update_zone_demand`. [05]
- Protocol decomposition (`TemperatureState` / `PIDState` / `HVACState`) where it's actually applied. [05]
- `StateRestorer` cleanly separates restoration with legacy-name handling. [06]
- `RestoreEntity` listener cleanup is thorough; no leaks on entity removal in the sensor layer. [06]

The architectural bones are right; the issues above are concentrated in (a) god-class accretion, (b) Protocol discipline drifting, and (c) restoration/migration getting behind feature growth.
