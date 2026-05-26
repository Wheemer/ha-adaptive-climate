# Multi-Zone Coordination Fix Plan Index (2026-05-25)

Source review: `docs/reviews/full-review-2026-05-25/05-multi-zone.md`

## Batches (related fixes — implement together)

- **Batch B1 (Critical-07 cluster):** C07 + H08 + H14 + A04 — central_controller concurrency refactor. All touch lock + task state in `central_controller.py`. Sequence: C07 → H08 + H14 (parallel) → A04 (depends on all).
- **Batch B2 (Weather entity):** C01 + M09 — night_setback_calculator weather lookup.
- **Batch B3 (Coordinator EMA/init):** C03 + H02 + H03 — coordinator init ordering and EMA filter.
- **Batch B4 (Auto-mode switching):** H06 + H07 + A03 — refactor `async_evaluate` responsibilities.
- **Batch B5 (Recovery deadline):** H13 + M11 — parsing validation + fallback chain.
- **Batch B6 (Coordinator decomposition):** M06 + A05 — extract ModeSync + further modules.
- **Batch B7 (Zone lifecycle):** A02 + H10 + M13 — pub/sub for register/unregister.

## Execution order (independent first → deepest dependents last)

| ID | Sev | Title | Depends on | Blocks |
|----|-----|-------|------------|--------|
| C01 | Crit | night_setback weather entity lookup | none | M09 |
| C02 | Crit | coordinator async_cleanup not wired | none | H10 |
| C04 | Crit | update_zone_demand drops state changes | none | H01 |
| C05 | Crit | _apply_house_mode ModeSync fan-out | none | none |
| C06 | Crit | NotificationManager datetime.now | none | none |
| C07 | Crit | _cancel_*_unlocked lock release | none | H08, H14 |
| C03 | Crit | coordinator init ordering | none | H02 |
| H05 | High | forecast_hours alias falsy collapse | none | none |
| H09 | High | register_zone resets demand state | none | none |
| H11 | High | auto-learning piggybacks night transition | none | none |
| H12 | High | days comparison DST-unsafe | none | none |
| H13 | High | recovery_deadline validation | none | M11 |
| H04 | High | active_zone_setpoints reads effective target | none | none |
| H06 | High | last_switch updated on no-op | none | A03 |
| M01 | Med | transport_delay slug fragile | none | none |
| M02 | Med | aggregate_demand two passes | none | none |
| M03 | Med | HVACMode import inside function | none | L03 |
| M04 | Med | cooling supply rebuild config | none | none |
| M05 | Med | redeclared annotation in else | none | none |
| M06 | Med | extract ModeSync to module | none | A05 |
| M07 | Med | ModeSync broad except | none | none |
| M08 | Med | weather forecast shape validation | none | none |
| M10 | Med | parse_sunset_offset heuristic | none | none |
| M12 | Med | consume_transition single-shot | none | none |
| M13 | Med | CycleEventDispatcher mutation race | none | A02 |
| M14 | Med | CycleEvent TypeAlias | none | none |
| M15 | Med | TURN_OFF_DEBOUNCE not configurable | none | none |
| M16 | Med | consecutive_failures key | none | none |
| M17 | Med | solar_gain orientation cache | none | none |
| M18 | Med | update_heater turnoff trace verify | none | none |
| L01 | Low | unused datetime import | none | none |
| L02 | Low | import fallback comment | none | none |
| L04 | Low | aggregate demand dict keys enum | none | none |
| L05 | Low | _outdoor_temp_unsub type | none | none |
| L06 | Low | task field type param | none | none |
| L08 | Low | redundant auto_mode_switching_enabled | none | none |
| L09 | Low | night_setback try/except import | none | none |
| L10 | Low | days_at_maintenance_cap cadence | none | none |
| L11 | Low | magic minute offsets | none | none |
| L12 | Low | info log per cycle noisy | none | none |
| L13 | Low | notify_service validation | none | none |
| L14 | Low | notify failure counter | none | none |
| L15 | Low | helpers/registry NameError | none | none |
| L16 | Low | empty TYPE_CHECKING block | none | none |
| L17 | Low | TemperatureState Protocol private attrs | none | cross-stream (01,02) |
| A01 | Arch | NightSetbackManager private access | none | none |
| A06 | Arch | NotificationManager relocate | none | none |
| A07 | Arch | coordinator data immutable | none | none |
| H01 | High | _update_pending no exception handling | C04 | none |
| H02 | High | outdoor temp EMA zero-dt reset | C03 | H03 |
| H10 | High | unregister_zone leaks thermal_group | C02 | none |
| H08 | High | turnoff task field race | C07 | none |
| H14 | High | async_cleanup task finally races | C07 | A04 |
| H07 | High | get_state_attributes recompute | H06 | none |
| H03 | High | EMA Euler discretization | H02 | none |
| M09 | Med | delete weather fallback list | C01 | none |
| M11 | Med | end_time fallback may raise | H13 | none |
| L03 | Low | duplicate HVACMode import | M03 | none |
| L07 | Low | cleanup not last action doc | H14 | none |
| A03 | Arch | auto-mode split responsibilities | H06 | none |
| A02 | Arch | zone lifecycle pub/sub | M13 | H10 |
| A05 | Arch | coordinator decompose | M06 | none |
| A04 | Arch | central_controller _DeviceController | C07, H08, H14 | none |

## Cross-subsystem dependencies

- **L17** (TemperatureState Protocol): shared with `01-climate` and `02-pid` streams — coordinate Protocol refactor across reviewers.
- **C06** (NotificationManager `datetime.now`): aligns with cross-cutting Theme A (time handling) — see `02-pid/C01`, `04-learning/*`.
- **C02** (async_cleanup wiring): touches `__init__.py` — coordinate with `01-climate` lifecycle plans.
- **H04** (effective target leak): consumer-side fix may need plumbing from climate entity — see `01-climate` user-target tracking.
- **H11** (auto-learning grace): interacts with `01-climate` learning-grace override logic and `04-learning` learning gate semantics.
- **A02** (zone lifecycle events): emits events consumed by `01-climate` (mode_sync), thermal group managers — cross-cutting Theme G concurrency.
- **A04** (DeviceController): touches concurrency model shared with `03-heater` cycle tracking timing.
