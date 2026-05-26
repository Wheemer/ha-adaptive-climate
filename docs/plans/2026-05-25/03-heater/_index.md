# 03-Heater & Cycle Tracking — Plan Index

Execution order: independent items first, deepest dependents last. Cross-subsystem refs prefixed with stream (e.g. `04-learning/...`).

## Batches

- **Batch A (heater_controller refactor)**: H01 splits file; L02, L03, L04 + H02, H03 + A02 should land alongside or after H01 to avoid merge thrash.
- **Batch B (state machine fixes)**: C03, H04, M04, M08, then A01 (sole-owner refactor) on stabilized base.
- **Batch C (cycle metrics correctness)**: C04, C05, M02, M03, H07, H08 — all in `cycle_metrics.py` / `cycle_tracker.py`, mostly independent.
- **Batch D (HeatPipeline decision)**: C01 first; M05, L12, A05 all gated on the keep/delete decision.

## Plans

| ID | Sev | Title | Depends on | Blocks |
|----|-----|-------|------------|--------|
| C02 | Critical | is_active() crashes on missing entity | none | none |
| C04 | Critical | undershoot uses raw cold history | none | 04-learning UndershootDetector |
| C05 | Critical | heater_active_periods fabricated | none | none |
| H02 | High | float equality on PID difference | none | none |
| H03 | High | min_closed_time semantic / asymmetry | none | none |
| H07 | High | deque truncates long settling windows | none | none |
| H08 | High | outdoor temp history unbounded | H07 | none |
| H09 | High | heating-type max_settling_time unused | none | none |
| M01 | Medium | hvac_mode string compare | none | L08 |
| M02 | Medium | mode captured at finalization | none | none |
| M03 | Medium | inter_cycle_drift stale on abort | none | none |
| M06 | Medium | COOL polarity convention unclear | none | none |
| M07 | Medium | learning_store inline hass.data lookup | none | A03 |
| M08 | Medium | settling timeout not cancelled on cycle start | none | none |
| M09 | Medium | document demand-zero precedence | none | none |
| M10 | Medium | HA-import fallback too broad | none | none |
| M11 | Medium | contact pause ignores entity_id | none | none |
| M12 | Medium | preset_temp float key lookup | none | none |
| M13 | Medium | set_preset_temp stringly typed | none | none |
| L01 | Low | typing.Callable | none | none |
| L05 | Low | PWM time_on unbounded | none | none |
| L06 | Low | _calculate_mad double median | none | none |
| L07 | Low | cycle_tracker lazy imports | none | none |
| L08 | Low | cycle_metrics StrEnum compare | M01 | none |
| L09 | Low | info logging hot path | none | none |
| L10 | Low | async_create_task no ref | none | none |
| L11 | Low | EVENT_HEATER_CONTROL_FAILED constant | none | none |
| C01 | Critical | HeatPipeline dead code / docs | none | M05, L12, A05 |
| C03 | Critical | valve state machine stuck | none | H04, M04 |
| H04 | High | async_call_later stale hvac_mode | C03 | M04 |
| M04 | Medium | _emit_heating_started_delayed ignores _cycle_active | H04 | none |
| M05 | Medium | PWM transport_delay asymmetry | C01 | none |
| L12 | Low | HeatPipeline clamp invariant | C01 | none |
| H05 | High | _cycle_active / _has_demand not restored | none | 04-learning cycle_count, A06 |
| H01 | High | heater_controller.py > 800 lines | C01, C02, C03 | H06, L02, L03, L04, A02 |
| H06 | High | PWM writes private _has_demand | H01 | A03 |
| L02 | Low | PID clamp passthroughs indirection | H01 | none |
| L03 | Low | _increment_cycle_count signature | H01 | none |
| L04 | Low | redundant timer handle nulling | H01 | none |
| A02 | Arch | HeaterController takes concrete thermostat | H01 | A04 |
| A04 | Arch | PWMController takes thermostat (redundant) | A02 | none |
| A03 | Arch | cross-module private access | H06 | none |
| A06 | Arch | PWMController restart safety | H05 | none |
| A01 | Arch | bidirectional cycle-state coupling | H01, C03, H04, M08 | none |
| A05 | Arch | HeatPipeline linear model wrong | C01 | none |

## Cross-subsystem dependencies

- **C04** → `04-learning` UndershootDetector tuning (settling-window-only fixes false Ki ramps).
- **H05** → `04-learning` `_heating_cycle_count` persistence (summary item #4) and `01-climate/H06` state restore.
- **C01** → CLAUDE.md docs drift theme (summary #B); cross-cuts `04-learning` (overshoot split feature).
- **M07** → `01-climate` / coordinator DI pattern (same anti-pattern as `_coordinator` inline lookup).
- **H04** → `01-climate` async_set_hvac_mode lifecycle hook (cancel_pending_timers integration point).
