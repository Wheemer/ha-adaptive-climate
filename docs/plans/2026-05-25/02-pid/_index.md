# 02-PID Plans Index — 2026-05-25

Source: `docs/reviews/full-review-2026-05-25/02-pid-control.md`
Count: 5 Critical, 11 High, 15 Medium, 10 Low, 8 Architectural = **49 plans** (review issues 1-41 + 8 architectural).

## Batches (fix together — same file/feature)

- **Batch B1 — Integral clamp & mutation**: C03, C05, H10, M31, A01. Shared `clamp_integral()` method; all integral writers go through it.
- **Batch B2 — Bumpless transfer correctness**: C02, H07, M30, L40. Same restart path.
- **Batch B3 — NaN/negative validation**: H08, H09, H10, M22, A08. Cascading validation + test harness.
- **Batch B4 — KeManager Protocol cleanup**: M23, A02, M24, M28, M29. Delete callback paths, fix Protocol declarations.
- **Batch B5 — Ke gate continuity**: H14, L40, A05. Decision point.
- **Batch B6 — Setpoint boost hardening**: C03, H13, M31. Same file.
- **Batch B7 — Restoration correctness**: C04, C05, M25, A04. Persistence + per-mode audit.

## Execution Order (independents first, deepest dependents last)

| Plan | Sev | Title | Depends on | Blocks |
|------|-----|-------|------------|--------|
| C01 | Crit | PID wall-clock time → monotonic | none | A03 |
| C04 | Crit | restore_from_state drops cooling | none | none |
| H06 | High | _accumulate_integral negative jitter | none | none |
| H08 | High | set_pid_param silent ignore / NaN | none | H09 |
| H11 | High | Clock jump no cycle invalidation | none | L36 |
| H12 | High | Legacy restore silent ke=0 | none | none |
| H13 | High | Setpoint boost stale pid ref | none | none |
| H14 | High | Ke discontinuity at setpoint | none | L40, A05 |
| H15 | High | _dead_time_start None defense | none | none |
| H16 | High | decay_integral negative factor | none | none |
| M17 | Med | clear_samples incomplete | none | none |
| M18 | Med | Duplicate init fields | none | none |
| M19 | Med | None narrowing on time fields | none | none |
| M20 | Med | _migrate_history defaults zero | none | none |
| M21 | Med | Dedup rounding precision loss | none | none |
| M23 | Med | KeManager dual API paths | none | A02 |
| M25 | Med | KeManager persists monotonic ts | none | none |
| M26 | Med | HVAC mode string compare | none | none |
| M27 | Med | Module-global warning dict | none | L36 |
| M28 | Med | pid_tuning getattr Protocol bypass | none | M29, A02 |
| M30 | Med | Bumpless skip criteria order | C02 | none |
| L32 | Low | Type-hint inconsistencies | none | none |
| L33 | Low | Docstring inaccuracies | none | none |
| L34 | Low | clear_samples _derivative_filtered (no-op) | none | none |
| L35 | Low | MIN_DT_FOR_DERIVATIVE hard-coded | none | none |
| L37 | Low | Misleading empty-history error | none | none |
| L38 | Low | pid_tuning private attr mutation | none (coord `04-learning/C13`) | none |
| L39 | Low | Manual apply no metrics | none | none |
| L41 | Low | reset_clamp_state no caller | none (coord `03-heater`) | none |
| A06 | Arch | PID imports const fallback | none | none |
| A07 | Arch | ControlOutputManager protocol access | none | none |
| C02 | Crit | Bumpless double integral | none | H07, M30 |
| C03 | Crit | Setpoint boost bypasses clamp | none | C05, M31, H10, A01 |
| H07 | High | Bumpless skip stale integral | C02 | none |
| H09 | High | Gains manager no validation | H08 | M22, A08 |
| H10 | High | scale/decay integral no validation | C03 | none |
| C05 | Crit | Restored integral not clamped | C03 | none |
| M22 | Med | PIDTuningManager validation | H09 | none |
| M24 | Med | Ke apply order | H09 | none |
| M29 | Med | pid_tuning mutates preheat internals | M28 | none |
| M31 | Med | Boost cap ignores headroom | C03 | none |
| L36 | Low | Clock jump no metric | M27, H11 | none |
| L40 | Low | Ke discontinuity + bumpless | H14 | none |
| A05 | Arch | Ke gate undocumented | H14 | none |
| A02 | Arch | KeManager dual API cleanup | M23 | none |
| A03 | Arch | Sampling-period bifurcation | C01 | none |
| A04 | Arch | Restore HEAT-only gap | C04 | none |
| A01 | Arch | Integral mutations uncentralized | C03 | none |
| A08 | Arch | No NaN/Inf test harness | H08, H09, H10 | none |

## Cross-subsystem dependencies

- **H11** ↔ `03-heater/H22` (cycle event coupling for clock_jump invalidation)
- **L38** ↔ `04-learning/C13` (mode-confused auto_apply counter — joint fix)
- **L41** ↔ `03-heater` (cycle tracker IDLE→HEATING event for reset_clamp_state)
- **C04 / A04** ↔ `04-learning` mode-awareness audit (cooling restoration uniform)
- **M25** ↔ `04-learning` UndershootDetector monotonic-persist (same antipattern)

## Unresolved questions

- H11: New event bus vs existing `CycleEventDispatcher`?
- H14: `cold_tolerance` for smooth Ke gate — configurable or fixed 0.5°C?
- A01: Separate `IntegralManager` or extend `PIDGainsManager`? History storage cost?
- A03: Confirm sampling-period mode has zero callers before deletion.
