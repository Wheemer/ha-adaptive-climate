# 01 Climate Orchestration — Fix Plan Index

Source review: `docs/reviews/full-review-2026-05-25/01-climate-orchestration.md`

Total plans: 53 (Critical 5, High 14, Medium 16, Low 18, Architectural 10).

## Cross-subsystem dependencies

- C02/C03 touch `coordinator.get_transport_delay_for_zone` and `ManifoldRegistry` — coordinate with `05-multizone`.
- A06 depends on `CycleEventDispatcher` (05-multizone) — needs new event type.
- L17 + C01 share a class of mutation races also surfacing in 02-pid (`set_pid_param`) and 06-sensors (`state_restorer` set_hvac_mode validation).
- A02/A09 (Protocol commit) is a cross-stream theme — references in `02-pid`, `03-heater`, `04-learning`, `05-multizone`.
- H05 (`timedelta.seconds` → `total_seconds`) likely needs grep audit beyond this subsystem.

## Batches (fix together)

- **Batch B1 — Mode mutation race:** C01 + H11 + M03 + M15 + L17 + A07 (all touch async set_* mode/temp flow and `_temp_lock`).
- **Batch B2 — Transport delay correctness:** C02 + C03 + H07 + M14 + A06 (unit + lookup + reset duplication + event-based push).
- **Batch B3 — Protocol/private access cleanup:** H02 + L12 + L18 + L19 + L20 + A02 + A03 + A09 (single Protocol discipline pass).
- **Batch B4 — Config wiring + typing:** C04 + H05 + A08 (schema audit then typed dataclass).
- **Batch B5 — God-class split:** M01 + A01 + A10 (extraction).
- **Batch B6 — Inline lookup refactor:** H06 + M12 (cached accessors).

## Execution order

Sorted: independent leaves first → deepest dependents last.

| ID | Severity | Title | Depends on | Blocks | Batch |
|----|----------|-------|------------|--------|-------|
| L01 | Low | Dead ABC comment | none | none | — |
| L02 | Low | datetime TYPE_CHECKING import | none | none | — |
| L03 | Low | NUMBER_DOMAIN magic string | none | none | — |
| L04 | Low | async_setup_platform self-rename | none | none | — |
| L05 | Low | Debug log config dict | none | none | — |
| L06 | Low | should_poll bool annotation | none | none | — |
| L07 | Low | Unnecessary getattr guard | none | none | — |
| L08 | Low | Pyright ignore rationale | none | none | — |
| L09 | Low | Emoji in notifications | none | none | — |
| L10 | Low | Preheat unsub typing | none | none | — |
| L11 | Low | PID int vs float init | none | none | — |
| L15 | Low | Init info-log frequency | none | none | — |
| L16 | Low | Unused imports in __init__.py | none | none | — |
| L18 | Low | Protocol _hvac_mode nullable | none | A09 | B3 |
| L19 | Low | Protocol untyped tuple | none | A09 | B3 |
| L20 | Low | Protocol gains_manager bare object | none | A09 | B3 |
| L14 | Low | zone_id slug collision | none | none | — |
| H01 | High | Dead restore wrappers | none | none | — |
| H03 | High | Learning gate private patch | none | none | — |
| H04 | High | sampling_period=0 fallback | none | none | — |
| H05 | High | timedelta.seconds truncation | none | none | B4 |
| H08 | High | control_heating time_func arg | none | none | — |
| H09 | High | Sensor timestamp advances on UNAVAILABLE | none | none | — |
| H10 | High | Duty accumulator magic number | none | A10 | — |
| H11 | High | set_hvac_mode broken annotation | none | M03 | B1 |
| H12 | High | Label/area clobbering | none | none | — |
| H13 | High | assert in production | none | none | — |
| H14 | High | Local import StatusManager | none | M13 | — |
| C03 | Critical | Manifold zone_id mismatch | none | C02 | B2 |
| C04 | Critical | Humidity/sleep config not wired | none | A08 | B4 |
| C05 | Critical | f-string `.4f` on string | none | none | — |
| M02 | Medium | `if True in list` antipattern | none | none | — |
| M05 | Medium | _saved_target_temp falsy | none | none | — |
| M06 | Medium | HEAT_COOL mismatch | none | none | — |
| M07 | Medium | Pause counter overcount | none | none | — |
| M08 | Medium | TemperatureUpdateEvent spam | none | none | — |
| M09 | Medium | Humidity decay elapsed unbounded | none | A10 | — |
| M10 | Medium | Mixed falsy / is not None | none | none | — |
| M11 | Medium | stored_data not popped | none | none | — |
| M13 | Medium | Imports inside functions | H14 | none | — |
| M16 | Medium | _ke_controller silent failure | none | none | — |
| L13 | Low | Handler await vs create_task | none | none | — |
| H06 | High | hass.data inline lookups | none | A04 | B6 |
| M12 | Medium | get_adaptive_learner closure | H06 | none | B6 |
| H02 | High | Private attribute reach-through | none | A01, A02, A03 | B3 |
| L12 | Low | Undershoot multiplier encapsulation | H02 | none | B3 |
| M04 | Medium | Dead _set_ke / _set_target_temp | none | A03 | B3 |
| C01 | Critical | HVAC mode switch race | none | H01, M03, M15, L17, A07 | B1 |
| L17 | Low | set_integral event race | C01 | none | B1 |
| M15 | Medium | ModeChangedEvent skipped | C01 | none | B1 |
| M03 | Medium | Sync set_hvac_mode divergent | C01, H11 | none | B1 |
| C02 | Critical | Valve actuation unit confusion | C03 | M14, A06 | B2 |
| M14 | Medium | Valve int vs float | C02 | none | B2 |
| H07 | High | Duplicate transport-delay reset | C02 | A06 | B2 |
| A04 | Architectural | HVAC mode multiple truths | none | none | — |
| A05 | Architectural | Restoration sequencing fragile | none | none | — |
| A07 | Architectural | asyncio.Lock inconsistent | C01 | none | B1 |
| A06 | Architectural | Manifold transport delay 3 paths | C02, C03, H07 | none | B2, **cross 05-multizone** |
| A08 | Architectural | parameters dict typed config | C04 | none | B4 |
| A10 | Architectural | Tunables scattered | H10, M09 | none | B5 |
| M01 | Medium | climate.py line cap | H02 | A01 | B5 |
| A02 | Architectural | Protocol vestigial | H02 | A03, A09, **cross 02/03/04/05** | B3 |
| A03 | Architectural | Setter callback busywork | A02, H02 | none | B3 |
| A09 | Architectural | Protocol exposes entire entity | A02, L18, L19, L20 | none | B3 |
| A01 | Architectural | God object | M01, H02, A02, A03 | none | B5 |

## Notes

- "Cross 05-multizone" = needs new `TransportDelayChangedEvent` in `CycleEventDispatcher` owned by coordinator.
- "Cross 02/03/04/05" for A02 = Protocol discipline applies system-wide; coordinate stream-wide.
- B1, B2, B3 should each ship as single PRs to keep regression-surface scoped.
