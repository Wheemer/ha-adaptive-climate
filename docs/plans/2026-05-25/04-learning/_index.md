# Plan Index: 04-learning (2026-05-25)

70 issues. Batches noted in **Batch** column. Sort = execution order (independent first).

## Suggested batches

- **B-SER** (serialization basics): C06 → C05 → C10 → C09 → A03
- **B-UNDERSHOOT**: C07 → C08 → H14, H15, H16 → M15, M16
- **B-HUMIDITY**: H04 → H03 → H01, H02, M17 → L16, L17
- **B-PREHEAT**: H05 → H06 → M19, L13, L14, L15, L18 (preheat) → H07
- **B-VALIDATION**: M03 → H12 → M04 → L18 → L19 → H13
- **B-CONTRIB**: C11 → H10 → M06, M07 → L20 → M21 (after H11)
- **B-LOWHANGING**: L03, L05, L08, L10, L11, L22, L24, L26, L27 (independent micro-cleanups)
- **B-MODE-COUNT**: C04, C03 (mode counters)
- **B-REFACTOR**: H17 → L01 → C01 → A01 → A04, A05, A06

## Table (execution order)

| ID | Severity | Title | Batch | Depends on | Blocks |
|----|----------|-------|-------|------------|--------|
| C06 | Critical | format_version int/str mismatch | B-SER | none | C05 |
| C04 | Critical | cycle_count not persisted | B-MODE-COUNT | none | none |
| C03 | Critical | Mode-confused auto-apply counter | B-MODE-COUNT | none | none |
| C02 | Critical | Validation ISO string > datetime | — | none | C03(wiring) |
| C07 | Critical | Ki cap doc drift (3.0 → 2.0) | B-UNDERSHOOT | none | C08 |
| C10 | Critical | Monotonic float serialized as garbage | B-SER | none | C09 |
| C11 | Critical | Poor cycle doesn't rebate contribution cap | B-CONTRIB | none | H10 |
| H01 | High | Forced humidity resume leak | B-HUMIDITY | none | none |
| H02 | High | Humidity pause_start stale ts | B-HUMIDITY | none | none |
| H04 | High | Humidity deque unbounded | B-HUMIDITY | none | H03 |
| H05 | High | Preheat bin_key shape validation | B-PREHEAT | none | H06 |
| H07 | High | Preheat cold-soak parens | B-PREHEAT | none | none |
| H08 | High | heating_rate _last_session_avg_duty uninit | — | none | none |
| H09 | High | heating_rate is_stalled fresh-session FP | — | none | none |
| H11 | High | Floor scaling magic 0.8 | — | none | A07 |
| H13 | High | Validation outdoor time pruning | B-VALIDATION | none | none |
| H16 | High | Undershoot enum string drift | B-UNDERSHOOT | none | none |
| H17 | High | ConfidenceTracker dead code | B-REFACTOR | none | C01 |
| M01 | Med | recent_cycles window scaling | — | none | none |
| M02 | Med | Inconsistent robust_average | — | none | none |
| M03 | Med | Empty overshoot → 0 false-tuned | B-VALIDATION | none | H12 |
| M05 | Med | Rate-based undershoot unwired | B-UNDERSHOOT | none | none |
| M10 | Med | Bare fromisoformat — 3 sites | — | none | H06 |
| M11 | Med | Manifold parse logging | — | none | none |
| M13 | Med | robust_stats min_valid_count docs | — | none | none |
| M14 | Med | MAD=0 tie-breaking | — | none | none |
| M18 | Med | heating_rate zero-duration | — | none | none |
| M19 | Med | bin storage deque maxlen | B-PREHEAT | none | none |
| M20 | Med | cycle_weight delta_multiplier clamp | — | none | none |
| M22 | Med | learning_gate broad except | — | none | L26 |
| M23 | Med | learning_gate default heat | — | none | none |
| M24 | Med | milestone idle transitions | — | none | none |
| M25 | Med | comfort_degradation cooldown | — | none | none |
| M26 | Med | comfort_degradation time-window | — | none | none |
| C05 | Critical | Destructive migration | B-SER | C06 | A03 |
| C08 | Critical | Undershoot cumulative negative | B-UNDERSHOOT | C07 | none |
| C09 | Critical | Undershoot cooldown monotonic restart | B-SER | C10 | none |
| H03 | High | Humidity stabilizing→spike needs 2 reads | B-HUMIDITY | H04 | none |
| H06 | High | Preheat from_dict no error guard | B-PREHEAT | H05 | none |
| H10 | High | Penalty not weighted | B-CONTRIB | C11 | none |
| H12 | High | Validation baseline=0 noise rollback | B-VALIDATION | none | M03 |
| H14 | High | Undershoot cap no-op applied | B-UNDERSHOOT | C08 | none |
| H15 | High | Undershoot realtime counter no decay | B-UNDERSHOOT | none | none |
| M04 | Med | Validation dual-condition slow degrade | B-VALIDATION | none | none |
| M06 | Med | Contribution tracker negative room | B-CONTRIB | C11 | none |
| M07 | Med | Heating rate hard cap | B-CONTRIB | none | none |
| M08 | Med | Auto-apply "stable" ambiguous | — | none | none |
| M09 | Med | AutoApplyGateResult dataclass | — | none | none |
| M12 | Med | Persistence v1-v5 no migrate | — | C05 | A03 |
| M15 | Med | Undershoot reset cycle | B-UNDERSHOOT | none | none |
| M16 | Med | Thermal debt cap type-agnostic | B-UNDERSHOOT | none | none |
| M17 | Med | Humidity peak init | B-HUMIDITY | none | none |
| M21 | Med | Recovery cycle hysteresis | — | H11 | none |
| L01 | Low | Backward-compat aliases | B-REFACTOR | none | C01 |
| L02 | Low | HVACMode=None default | — | none | A09 |
| L03 | Low | Inline imports clear_history | B-LOWHANGING | none | none |
| L04 | Low | reset() methods | — | none | none |
| L05 | Low | get_previous_pid zombie | B-LOWHANGING | none | A02 |
| L06 | Low | misclassification comment | — | none | none |
| L07 | Low | TODO rot | — | none | none |
| L08 | Low | Inline imports heating_rate | B-LOWHANGING | none | none |
| L09 | Low | from_dict heating_type arg | — | none | none |
| L10 | Low | Disturbance logger wrapper | B-LOWHANGING | none | none |
| L11 | Low | Disturbance magic numbers | B-LOWHANGING | none | none |
| L12 | Low | Disturbance solar units | — | none | none |
| L13 | Low | Preheat prune counter | B-PREHEAT | none | none |
| L14 | Low | Preheat expire list comp | B-PREHEAT | none | none |
| L15 | Low | Preheat median caching | B-PREHEAT | none | none |
| L16 | Low | Humidity should_pause docs | B-HUMIDITY | none | none |
| L17 | Low | Humidity time_until_resume | B-HUMIDITY | none | none |
| L18 | Low | Validation baseline or falsy | B-VALIDATION | H12 | none |
| L19 | Low | Validation kp zero divide | B-VALIDATION | none | none |
| L20 | Low | cycle_weight dead undershoot | B-CONTRIB | H10 | none |
| L21 | Low | auto_apply unknown heating_type | — | none | none |
| L22 | Low | floor_physics isinstance (WONTFIX?) | L | none | none |
| L23 | Low | floor_physics KeyError guard | L | none | none |
| L24 | Low | Persistence magic int | B-LOWHANGING | none | none |
| L25 | Low | Persistence lambda capture | — | none | none |
| L26 | Low | learning_gate safe_check helper | — | M22 | none |
| L27 | Low | Pluralization util | — | none | none |
| C01 | Critical | Split learning.py god file | B-REFACTOR | C05, C06, C09, H17, L01 | A01 |
| A02 | Arch | Dead-code audit | — | H17, M05, L05, L20 | none |
| A03 | Arch | Migration story | — | C05, C06, M12 | none |
| A07 | Arch | Magic numbers → constants | — | H11 | none |
| A08 | Arch | Time handling uniformity | — | C09, C10 | A04 |
| A09 | Arch | Pyright strict adaptive/ | — | L02 | none |
| A10 | Arch | CLAUDE.md doc drift | — | C07, C05, A03 | none |
| A01 | Arch | Extract LearningCoordinator | B-REFACTOR | C01, L01, H17 | A04, A05, A06 |
| A04 | Arch | Cross-restart state matrix | — | A01, A08 | none |
| A05 | Arch | Mode-awareness audit | — | A01 | none |
| A06 | Arch | LearningHealthMonitor | — | A01 | none |

## Cross-subsystem dependencies (explicit)

- **C02** (`validation.py` ISO compare) consumes `pid_history` written by `02-pid` PIDGainsManager — coordinate with `02-pid` plans on enum `.value` (see H16).
- **C03** (mode counter) interacts with `managers/pid_tuning.py` — likely overlaps with `02-pid` PID-tuning plans.
- **C04** (cycle_count persistence) interacts with `06-sensors` (status attribute reads `learning.status`) — verify status sensor stable across restart.
- **C09/C10/A08** (time handling) pairs with `02-pid` (PID `time()` → `monotonic()` ship-stopper #1 from summary).
- **A03** (migration) interacts with restart sequencing in `01-climate` (climate restoration path).
- **H16** (PIDChangeReason enum) — confirm enum `.value` strings with `02-pid/PIDGainsManager` owner.
