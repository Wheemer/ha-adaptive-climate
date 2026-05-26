# Master Execution Graph — 2026-05-25

378 plan files across 6 subsystems. Each plan = one file at `<subsystem>/<sev><num>-<slug>.md`. Indexes per subsystem in `<subsystem>/_index.md`.

| Stream | Crit | High | Med | Low | Arch | Total |
|--------|------|------|-----|-----|------|-------|
| 01-climate | 5 | 14 | 16 | 18 | 10 | 63 |
| 02-pid | 5 | 11 | 15 | 10 | 8 | 49 |
| 03-heater | 5 | 9 | 13 | 12 | 6 | 45 |
| 04-learning | 11 | 17 | 26 | 27 | 10 | 91 |
| 05-multizone | 7 | 14 | 18 | 17 | 7 | 63 |
| 06-sensors | 7 | 14 | 20 | 16 | 7 | 64 |
| **Total** | **40** | **79** | **108** | **100** | **48** | **375** |

---

## Decision points (resolve FIRST — block multiple waves)

These need a human/expert call before downstream plans can finalize.

| # | Decision | Blocks | Owner |
|---|----------|--------|-------|
| D1 | **HeatPipeline: wire it up or delete?** Docs claim active, code unreachable. | `03-heater/C01,M05,L12,A05`; CLAUDE.md doc updates | hvac-expert + user |
| D2 | **Ki cap value** — 2.0 (docs) or 3.0 (code)? Floor-hydronic recovery may need >2.0. | `04-learning/C07,C08,H14,H15` | hvac-expert |
| D3 | **Migration strategy** — implement v5→v10 migrations or freeze schema with breaking-change docs? | `04-learning/C05,A03,M12`; restart sequencing | user |
| D4 | **Integral mutation centralization** — new `IntegralManager` or extend `PIDGainsManager`? | `02-pid/A01` and all B1 batch | architect |
| D5 | **Protocol discipline level** — commit fully (no private reach-through) or remove `ThermostatState`? | `01-climate/A02`; `02/03/04/05` Protocol items | architect |
| D6 | **Mixin / god-class split** — extract per CLAUDE.md 800-line rule or keep current structure? | `01-climate/A01`; `04-learning/A01`; `03-heater/H01`; `coordinator.py` extraction | architect |
| D7 | **Cooling undershoot detection** — wanted, or keep heating-only? | `04-learning/A05` | hvac-expert |
| D8 | **Penalty path weighting** — mirror reward (weighted+capped) or keep flat 0.05? | `04-learning/C11,H10,M06,M07` | hvac-expert |
| D9 | **`auto-learning setback` overhaul** — separate path or piggyback on regular night-setback? | `05-multizone/H11`; `04-learning` grace logic | architect + hvac-expert |
| D10 | **`_time_below_target` decay** — smooth decay or hard reset within tolerance? | `04-learning/H15,M15` | hvac-expert |

---

## Wave plan (parallelism-maximizing)

Each wave = work that can ship without waiting on any later wave. Within a wave, items grouped by **batch** (same-file or same-feature) ship together as one PR.

### Wave 0 — Cross-cutting no-deps (can start parallel TODAY)

These are mechanical, low-risk, no architectural decisions. Dispatch 6+ engineers in parallel.

**Theme A — Time handling sweep** (one engineer, single PR):
- `02-pid/C01` — PID `time()` → `monotonic()` (THE ship-stopper)
- `05-multizone/C06` — `NotificationManager` `datetime.now()` → `time.monotonic()`
- `04-learning/C09,C10,A08` — remove monotonic-float persistence in UndershootDetector/KeManager
- `02-pid/M25` — KeManager monotonic restore
- `04-learning/M10` — `fromisoformat` error handling (3 sites)

**Theme B — Input validation** (one engineer):
- `02-pid/H08,H09,H10,M22` — NaN/Inf/negative guards in `set_pid_param`, `set_gains`, `scale_integral`, `decay_integral`, `PIDTuningManager.async_set_pid`
- `06-sensors/H14` — validate `set_hvac_mode(state)` against `HVACMode.__members__`
- `05-multizone/H13` — `recovery_deadline` parse validation
- `02-pid/A08` — add NaN-injection test harness (last)

**Theme C — Quick-win critical** (one engineer, multiple small PRs):
- `05-multizone/C01,M09` — weather entity lookup (delete fallback list)
- `05-multizone/C02` — wire `coordinator.async_cleanup()` into `async_unload_entry`
- `04-learning/C02` — validation ISO timestamp parsing + re-wire real `pid_history`
- `04-learning/C04` — persist `_heating_cycle_count` / `_cooling_cycle_count`
- `04-learning/C06` — `format_version` int/str unification (pre-req for `C05`)
- `06-sensors/H11,H12` — solar gain hemisphere fix
- `01-climate/C05` — `f-string ':.4f'` crash on missing key

**Theme D — Independent Low cleanup** (one engineer, single sweep PR):
- All Low items with `Depends on: none` across all streams (~60 items). Dead comments, unused imports, type-hint fixes, magic-number naming, log-level demotions, docstring fixes.

**Theme E — Cycle metrics correctness** (one engineer):
- `03-heater/C04` — undershoot uses settling-window-only history
- `03-heater/C05` — `heater_active_periods` from real device on/off times
- `03-heater/C02` — `is_active()` per-entity null guard
- `03-heater/M02,M03,H07,H08,H09` — same files, cohesive PR

**Theme F — Service registration & misc** (one engineer):
- `06-sensors/C01,C02,H04,H07` — `services/scheduled.py` batch
- `06-sensors/H05` — register debug services or remove from `services.yaml`
- `06-sensors/C06,M04` — currency parsing for MONETARY device_class
- `06-sensors/C07,H10,M05` — week boundary + meter-reset + BTU conversions

### Wave 1 — Critical correctness depending on Wave 0

After Wave 0 batches merge:

**Concurrency cluster** (depends on Wave 0 Theme C `async_cleanup`):
- `01-climate/C01,H11,M03,M15,L17,A07` — `async_set_hvac_mode` lock-protect (climate B1)
- `05-multizone/C07,H08,H14,A04` — `central_controller` lock dance refactor (multizone B1)
- `05-multizone/C04,H01` — `update_zone_demand` rerun flag
- `05-multizone/C05` — `_apply_house_mode` sets `ModeSync._sync_in_progress`
- `05-multizone/C03,H02,H03` — coordinator init ordering + EMA fix (multizone B3)

**Restoration cluster** (depends on D3 migration decision):
- `04-learning/C05,A03,M12` — implement migrations or freeze schema (B-SER)
- `02-pid/C04,A04` — restore COOL gains
- `02-pid/C05` — clamp restored integral on first calc
- `03-heater/H05` — persist `_cycle_active`/`_has_demand`

**Mode-counter cluster** (joint with `02-pid` ownership):
- `04-learning/C03` + `02-pid/L38` — fix mode-confused `_auto_apply_count` together
- `04-learning/A05` — mode-awareness audit (depends on D7)

**Undershoot detector cluster** (depends on D2 Ki cap decision):
- `04-learning/C07,C08,H14,H15,H16,M15,M16` (B-UNDERSHOOT)
- `03-heater/C04` already done in Wave 0 feeds clean data here

**Multi-zone correctness** (depends on Wave 0):
- `05-multizone/C04` — `update_zone_demand` rerun flag (was in Wave 1 concurrency)
- `05-multizone/H04` — active_zone_setpoints reads user setpoint (needs `01-climate` plumbing)
- `05-multizone/H06,H07,A03` — auto-mode switching split (B4)
- `05-multizone/H11` — auto-learning piggyback (depends on D9)
- `05-multizone/H09,H10` — register_zone state + unregister thermal group leak

### Wave 2 — Architectural decisions implementation

After D1, D4, D5, D6, D9 resolved:

- `03-heater/C01,M05,L12,A05` — HeatPipeline wire-or-delete (D1)
- `02-pid` Batch B1 — `IntegralManager` or `PIDGainsManager` extension (D4)
- `02-pid` Batches B2-B7 — bumpless transfer, Ke gate, KeManager Protocol cleanup
- `01-climate` Batch B2 — transport-delay unit + event-driven push (cross with `coordinator`)
- `01-climate` Batch B3 — Protocol discipline pass (cross-cuts 02/03/04/05) (D5)
- `01-climate` Batch B4 — typed config dataclass

### Wave 3 — Refactors & file splits

After D6 resolved:

- `01-climate/M01,A01,A10` — split `climate.py` (1938 LOC)
- `04-learning/H17,L01,C01,A01` — split `learning.py` (1701 LOC), extract `LearningCoordinator`
- `03-heater/H01` — split `heater_controller.py` (1132 LOC), depends on Wave 1 state-machine fixes
- `05-multizone/M06,A05` — extract `ModeSync` to its own module
- `06-sensors/C05,A02` — split `state_attributes.py` (813 LOC)
- `05-multizone/A04` — collapse heater/cooler duplication into `_DeviceController`

### Wave 4 — Cross-cutting deferred work

- `06-sensors/M11,A01,L11` — unify `PauseDetector` (3 implementations today)
- `05-multizone/A02,M13,H10` — zone lifecycle pub/sub via `CycleEventDispatcher`
- `04-learning/A04,A05,A06` — cross-restart state matrix, mode-awareness audit, `LearningHealthMonitor`
- CLAUDE.md doc reconciliation pass (`04-learning/A10`; matches summary theme B)
- Test harness additions (`02-pid/A08`, `06-sensors/A04`)

---

## Parallel execution slots

Suggested team layout for Wave 0 + Wave 1 (~3-4 weeks of work):

| Slot | Engineer | Theme(s) | Concurrent with |
|------|----------|----------|-----------------|
| 1 | typescript-engineer | Wave 0 Theme A (time handling) | all others |
| 2 | software-engineer | Wave 0 Theme B (validation) | all others |
| 3 | software-engineer | Wave 0 Theme C (quick critical) | all others |
| 4 | software-engineer | Wave 0 Theme D (Low sweep) | all others |
| 5 | hvac-expert | Wave 0 Theme E (cycle metrics) | all others |
| 6 | software-engineer | Wave 0 Theme F (services/sensors) | all others |
| → | (sync point) | Wave 0 merges; D1-D10 decisions | — |
| 7 | software-engineer | Wave 1 concurrency cluster | restoration cluster |
| 8 | software-engineer | Wave 1 restoration cluster | concurrency cluster |
| 9 | hvac-expert | Wave 1 mode-counter + undershoot | independent |
| 10 | software-engineer | Wave 1 multi-zone correctness | independent |

Wave 2/3/4 require architectural decisions first; defer team scaling until D-resolutions land.

---

## Open questions (consolidated from per-subsystem indexes)

**Architectural (need owner call):**
- D1 HeatPipeline keep/delete — `03-heater/C01`
- D3 Migration story — `04-learning/A03`
- D4 IntegralManager vs PIDGainsManager extension — `02-pid/A01`
- D5 Protocol discipline level — `01-climate/A02`
- D6 God-class split scope — multiple
- D9 Auto-learning setback path — `05-multizone/H11`

**Domain / hvac-expert call:**
- D2 Ki cap 2.0 vs 3.0 — `04-learning/C07`
- D7 Cooling undershoot detection — `04-learning/A05`
- D8 Penalty path weighting — `04-learning/C11,H10`
- D10 `_time_below_target` decay style — `04-learning/H15`
- `02-pid/H14` — `cold_tolerance` for smooth Ke gate, configurable or fixed 0.5°C?
- `06-sensors/A06` — pause-counter reset-first vs reset-after-success preference

**Implementation detail / engineer call:**
- `02-pid/H11` — new event bus or extend `CycleEventDispatcher` for clock-jump?
- `02-pid/A03` — confirm sampling-period mode has zero callers before deletion
- `06-sensors/L16` — i18n epic timing
- `04-learning/C05/A03` — v5–v9 storage fixtures available, or synthesize from git?
- `04-learning/M05` — keep or delete `check_rate_based_undershoot`?

---

## How to execute

1. Resolve D1-D10 (an afternoon with hvac-expert + you).
2. Spawn Wave 0 engineers in parallel (6 slots) — all mechanical, low conflict surface.
3. Sync point: Wave 0 merges, regression-test suite passes, you decide on Wave 1 ordering.
4. Wave 1 — 4 engineers, ~1-2 weeks of work each.
5. Wave 2-4 are multi-month structural improvements; revisit after the first two waves stabilize the system.

The summary's 4-phase order (`docs/reviews/full-review-2026-05-25/00-summary.md`) maps roughly: Phase 1 = Wave 0 + critical bits of Wave 1; Phase 2 = rest of Wave 1; Phase 3 = Wave 2-3; Phase 4 = Wave 4 + observability.
