# 06-sensors-services fix plans index

Source review: `docs/reviews/full-review-2026-05-25/06-sensors-services.md`

## Batches

- **Batch B1 (state_attributes refactor):** C03 → C04 → C05 → A02 → H01 → H02. Same file + cascading splits.
- **Batch B2 (energy sensor):** C06 → M04, C07 → H10, M05 (UNIT_CONVERSIONS).
- **Batch B3 (pause detector):** M11 → A01 → L11.
- **Batch B4 (sensor coupling):** H08 → A03.
- **Batch B5 (services scheduled):** C01, C02, H04, H07 share file `services/scheduled.py`.
- **Batch B6 (UTC consistency):** M15 → L14.
- **Batch B7 (solar):** H11 → H12.

## Execution order (independent first, deepest dependents last)

| ID | Sev | Title | Depends on | Blocks |
|----|-----|-------|------------|--------|
| C01 | Crit | Weekly snapshot wrong ISO week | none | H04 |
| C02 | Crit | confidence_raw leaks between zones | none | none |
| C06 | Crit | Currency invalid for MONETARY | none | M04 |
| C07 | Crit | Week boundary uses UTC ISO Monday | none | H10, M05 |
| H03 | High | pid_history recorder bloat | none | none |
| H05 | High | Services registered only in debug | none | A05 |
| H06 | High | Vacation mode unsafe data access | none | none |
| H07 | High | PID recommendations fake baseline | none | none |
| H08 | High | Hardcoded sensor entity_ids | none | A03 |
| H09 | High | delta_t=0 dropped | none | none |
| H11 | High | Solar gain Northern-only | none | H12 |
| H13 | High | Private attr learning_grace_end | none | none |
| H14 | High | set_hvac_mode "unavailable" not validated | none (cross: `01-climate/H06`) | none |
| M01 | Med | Performance deque chatter | none | none |
| M02 | Med | Short cycles dropped hardcoded | none | none |
| M03 | Med | Zero cycle_time falsy drop | none | none |
| M06 | Med | zone_issues uncapped | none | none |
| M07 | Med | sensor_available default inverted | none | none |
| M08 | Med | Comfort score float no unit | none | none |
| M09 | Med | Comfort score deviation not scaled | none | none |
| M10 | Med | Weekday magic number | none | none |
| M12 | Med | actuator_wear None TypeError | none | none |
| M13 | Med | Actuator alert event flood | none | none |
| M14 | Med | Reports display_name title() | none | none |
| M15 | Med | status_manager mixes local+UTC | none | L14 |
| M16 | Med | should_pause bool wrap | none | none |
| M17 | Med | CONFIDENCE_TIER_3 >100 brittle | none | none |
| M18 | Med | demand_switch cycle_count lossy | none | none |
| M19 | Med | number.py no subscriber notify | none | none |
| M20 | Med | number.py min/max validation | none | none |
| L01 | Low | Sensor update loop not isolated | none | none |
| L02 | Low | Unused re-exports sensor.py | none | none |
| L03 | Low | heater_entity_id list warn | none | none |
| L04 | Low | Overshoot iterates full history | none | none |
| L05 | Low | _coordinator lookup not cached | none | none |
| L06 | Low | Comfort oscillation magic number | none | none |
| L07 | Low | health severity AttributeError | none | none |
| L08 | Low | actuator_wear task per change | none | none |
| L09 | Low | services bare except privacy | none | none |
| L10 | Low | Percent-change tiny denominator | none | none |
| L12 | Low | Fire-and-forget milestone task | none | none |
| L13 | Low | MagicMock guard in prod | none | none |
| L15 | Low | Integral restore bool passthrough | none | none |
| L16 | Low | Reports hardcoded English | none | none |
| A06 | Arch | Pause counter reset on failure | none | none |
| A07 | Arch | WeeklyReport.to_dict drops fields | none | none |
| H04 | High | %-d strftime not portable | C01 (batch B5) | none |
| H10 | High | Meter-reset vs rollover | C07 | none |
| M04 | Med | Currency drift on update | C06 | none |
| M05 | Med | BTU missing UNIT_CONVERSIONS | none (cross-ref C07 batch B2) | none |
| H12 | High | Cloud adjustment 10x overshoot | H11 | none |
| C03 | Crit | StatusManager rebuilt per read | none | C04, C05 |
| C04 | Crit | Double night-setback calc | C03 | none |
| C05 | Crit | state_attributes.py >800 lines | C03, C04 | A02 |
| H01 | High | Flat preheat/humidity attrs | C05 | H02 |
| H02 | High | Humidity dual representation | H01 | none |
| M11 | Med | is_paused duplicated 3 places | none | A01 |
| A01 | Arch | Unify PauseDetector | M11 | none |
| L11 | Low | Triple-nested try/except | M11 | none |
| L14 | Low | format_iso8601 wrapper | M15 | none |
| A02 | Arch | state_attributes god split | C05 | none |
| A03 | Arch | Sensor coupling via entity_id | H08 | none |
| A05 | Arch | Service response registration | H05 | none |
| A04 | Arch | Add sensor unit tests | C06, C07, M02, M08, M09, etc. | none |

## Cross-subsystem dependencies

- **H14** ↔ `01-climate/H06` — HVAC mode validation duplicated in climate restoration.
- **C03/C04** rely on `_status_manager` ownership likely covered in `01-climate` orchestration.
- **M11/A01** PauseDetector overlaps with `04-learning` learning-gate logic.
- **H03** pid_history cap also touched in `02-pid/PIDGainsManager` review.
- **C01/H04** scheduled report week math affects `04-learning` weekly-snapshot consumers.
