# Decision Resolutions — 2026-05-25

Resolutions for the 10 decision points called out in `00-execution-graph.md`. Engineers executing plans should treat these as binding unless explicitly overruled in plan-level notes.

---

## D1 — HeatPipeline: wire it up AND redesign the model first

**Decision:** Wire `HeatPipeline` into the live control loop, but **redesign the heat-delivery model first** — the current linear interpolation is wrong for real hydronic systems.

**Implementation order:**
1. Replace linear `committed_heat_remaining` with exponential rise/decay matched to thermal_time_constant.
2. Add `valve_opened()` / `valve_closed()` calls from `HeaterController.async_turn_on/off`.
3. Query `committed_heat_remaining` in `PWMController.calculate_adjusted_on_time`.
4. Wire `CycleMetricsRecorder` to split overshoot into controllable vs committed.

**Affects:** `03-heater/C01, M05, L12, A05`. ~2 weeks. Goes in Wave 2.

---

## D2 — Ki cap: 3.0x, fix the docs

**Decision:** Keep `MAX_UNDERSHOOT_KI_MULTIPLIER = 3.0`; update CLAUDE.md and any other docs that say 2.0x.

**Rationale:** Floor-hydronic chronic undershoot in cold weather genuinely needs >2.0x recovery headroom; users were complaining and the code was right.

**Affects:** `04-learning/C07` becomes a docs-only fix. `C08, H14, H15, M15, M16` proceed as planned (they're about correctness of the gate, not the cap value).

---

## D3 — Migrations: implement v5→v10 properly

**Decision:** Write per-version migration functions. Use git history to reconstruct old schemas; synthesize fixtures per version.

**Implementation order:**
1. Read git log for `learner_serialization.py` and `persistence.py` to recover schemas for v5, v6, v7, v8, v9.
2. Write one migration function per step (`_migrate_v5_to_v6`, etc.) and chain them.
3. Add a fixture per version under `tests/fixtures/learner_v{N}.json`.
4. Round-trip test: load each, migrate, verify post-migration shape and that downstream code works.

**Affects:** `04-learning/C05, A03, M12, C06`. ~3-5 days. Wave 1.

**Open follow-up:** v1-v4 in `persistence.py` get the same treatment.

---

## D4 — Extend PIDGainsManager → rename to PIDStateManager

**Decision:** Add integral mutation methods to the existing manager rather than create a new one. Rename to reflect broader scope.

**API additions:**
- `boost_integral(amount, reason: PIDChangeReason, metrics: dict | None)`
- `decay_integral(factor, reason, metrics)`
- `scale_integral(factor, reason, metrics)`
- `set_integral(value, reason, metrics)` — always re-clamps to `[out_min - E - F, out_max - E - F]`

All current writers (climate.py:1118/1221/1550, climate_control.py:93/167, pid_tuning.py:130/210/306/395, state_restorer.py:132, setpoint_boost.py:150/162, __init__.py:689) migrate to call these methods. History recorded automatically.

**Affects:** `02-pid/A01` and Batch B1 (C03, C05, H10, M31). ~2-3 days. Wave 2.

---

## D5 — Commit fully to ThermostatState Protocol

**Decision:** Trim Protocol to ~10 used methods, eliminate all cross-module private attribute reach-through, replace setter-callback pattern with Protocol method calls.

**Scope:**
- Audit every `self._*` reference made outside its owning class — convert to Protocol method or public property.
- Delete setter callback dictionaries; managers call typed Protocol methods.
- `HeaterController`, `KeManager`, `PIDTuningManager`, `ControlOutputManager` all accept `ThermostatState` (or narrower sub-protocols like `TemperatureState`, `PIDState`, `HVACState`).
- Trim Protocol to actually-used methods (~10 from current 30+).

**Affects:** `01-climate/A02, A03, A09, H02`; `02-pid/A02, A07, M23, M28`; `03-heater/A02, A04`; `04-learning/A02`; `05-multizone/L17`. Multi-week effort. Wave 2-3, after correctness fixes.

---

## D6 — Split only the >1000 LOC files

**Decision:** Split `climate.py` (1938), `learning.py` (1701), and `heater_controller.py` (1132). Leave `coordinator.py` (948), `state_attributes.py` (813), and `central_controller.py` (656) as documented exceptions with a top-of-file comment explaining why.

**Rationale:** The three giant files have clear extraction lines (per-feature handlers in climate, learner-coordinator pattern in learning, timer/cycle-counting split in heater). The other three are tightly cohesive; splitting would create artificial seams. Update CLAUDE.md line-limit rule to say "soft 800 / hard 1100" with explicit exceptions list.

**Affects:** `01-climate/M01, A01, A10`; `04-learning/H17, L01, C01, A01`; `03-heater/H01`. Wave 3. ~1 month total.

**De-scoped:** `05-multizone/M06, A05` (extract ModeSync); `06-sensors/C05, A02` (split state_attributes). Mark plans as deferred.

---

## D7 — Cooling undershoot: heating-only, document

**Decision:** Keep `UndershootDetector` heating-only. Add a one-line docstring noting the limitation. No new code.

**Rationale:** Cooling is a minor use case in this codebase (NL/EU energy-rating focus). Doubling the surface area for unproven benefit isn't worth it. Revisit if users report cooling Ki issues.

**Affects:** `04-learning/A05` becomes a docs-only update. Mark as Wave 0 D-sweep.

---

## D8 — Penalty path: mirror weighted reward + skip on disturbance

**Decision:** Penalty uses the same weight formula as reward (`base × delta_multiplier × outcome_factor`), but skip the penalty entirely if the disturbance detector flagged the cycle.

**Implementation:**
1. Replace `learning.py:1208` flat `0.05` with `weighted_penalty = -CONFIDENCE_INCREASE_PER_GOOD_CYCLE * cycle_weight`.
2. Apply the same `confidence_contribution` cap routing as rewards.
3. Before applying penalty, check `disturbance_detector.was_cycle_disturbed(metrics)` — if true, skip entirely (return 0).
4. Also: when penalty applied, **rebate the contribution cap** by an equal amount (resolves `04-learning/C11`).

**Affects:** `04-learning/C11, H10, M06, M07, L20`. ~2-3 days. Wave 1.

---

## D9 — Auto-learning setback: separate path, no piggyback

**Decision:** Auto-learning setback gets its own override type (`auto_learning_window`) and its own grace logic. Users without configured night-setback never see spurious grace periods.

**Implementation:**
1. Add `AutoLearningOverride` to `status.overrides[]` with type `auto_learning_window`, fields `delta`, `window_end`.
2. Move grace-handling out of `NightSetbackManager` into a new `AutoLearningSetbackController`.
3. The regular night-setback path no longer fires for auto-learning activations.
4. Status attribute schema updated.

**Affects:** `05-multizone/H11`; `04-learning` learning-gate semantics; `06-sensors` state_attributes schema. ~3-4 days. Wave 1.

---

## D10 — `_time_below_target`: smooth exponential decay, tau by heating type

**Decision:** Continuous decay with tau scaled by thermal mass.

**Implementation:**
- Add `UNDERSHOOT_TBT_DECAY_TAU = {floor_hydronic: 4h, radiator: 2h, convector: 1h, forced_air: 30min}` to const.py.
- In `update_real_time`, decay `_time_below_target *= exp(-dt / tau)` on every call (not just when above setpoint).
- Remove the "only resets when temp goes above setpoint" branch.

**Affects:** `04-learning/H15, M15`. ~1 day. Wave 1.

---

## D11 — Ke external term smooth gate: fixed 0.5°C `cold_tolerance`

**Decision:** Reuse the existing `cold_tolerance` constant. Multiply Ke contribution by `max(0, min(1, error/cold_tolerance + 1))`. No new config.

**Affects:** `02-pid/H14, L40, A05`. ~1 day. Wave 2.

---

## D12 — Pause counter reset: AFTER successful snapshot save

**Decision:** Wrap snapshot-save + counter-reset in try/finally so reset only happens after the save succeeds. If save fails, counters carry over and next week double-counts (acceptable degradation).

**Affects:** `06-sensors/A06`. Trivial. Wave 0.

---

## D13 — Clock-jump invalidation: extend `CycleEventDispatcher`

**Decision:** Add `ClockJumpEvent` to the existing pub/sub. `CycleTracker` subscribes and discards the in-flight cycle when fired. `ControlOutputManager` emits the event when `actual_dt` is clamped to 0.

**Affects:** `02-pid/H11, M27, L36`; `03-heater` cycle tracker subscription. ~1 day. Wave 1.

---

## D14 — `check_rate_based_undershoot`: wire it up

**Decision:** Hook into `check_undershoot_adjustment` alongside realtime + cycle modes. Third independent signal catches gradual underperformance the other two miss.

**Affects:** `04-learning/M05` upgraded from delete-or-keep to wiring task. ~1 day. Wave 1.

---

## D15 — Sampling-period PID mode: keep it, fix monotonic

**Decision:** Don't delete the sampling-period branch in `PID.calc()`. Switch its `time()` call to `time.monotonic()` along with the event-driven path (D2 ship-stopper #1 already covers most of this).

**Affects:** `02-pid/A03` becomes "fix not delete". Folds into `02-pid/C01` (time-handling sweep). No separate plan.

---

## D16 — i18n: defer to v1.0 release

**Decision:** Keep hardcoded English. Create a deferred-work tracking issue. Revisit if/when integration ships v1.0 / GA.

**Affects:** `06-sensors/L16`. Closed as wontfix-for-now with a tracking note in the plan file.

---

## Cascading plan changes

The decisions above downgrade or close several plans:

| Plan | Was | Now |
|------|-----|-----|
| `04-learning/C07` | Critical: lower cap to 2.0x | Docs-only update (D2) |
| `04-learning/A05` | Architectural: mode-awareness audit | Docs-only note (D7) |
| `05-multizone/M06` | Medium: extract ModeSync | Deferred per D6 |
| `05-multizone/A05` | Architectural: coordinator decompose | Deferred per D6 |
| `06-sensors/C05` | Critical: state_attributes >800 lines | Documented exception per D6 |
| `06-sensors/A02` | Architectural: state_attributes god split | Deferred per D6 |
| `02-pid/A03` | Architectural: delete sampling-period mode | Fix to monotonic, keep mode (D15) |
| `04-learning/M05` | Medium: delete-or-keep rate-based undershoot | Wire it into check_undershoot_adjustment (D14) |
| `06-sensors/L16` | Low: i18n hardcoded English | Deferred to v1.0 (D16) |

The execution graph (`00-execution-graph.md`) stands; these resolutions just settle the open variables for the engineers implementing each plan.
