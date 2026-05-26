# Codebase Overview & Refactoring Analysis

## Overview

Adaptive Climate is a Home Assistant custom component implementing PID-based thermostat control with adaptive learning, multi-zone coordination, and physics-based initialization. The codebase totals ~32,300 lines of source code across 77 Python files, with ~70,700 lines of tests across 104 test files.

## File Structure & Sizes

### Files Over 800 Lines (Violating Project Max)

| File | Lines | Primary Concern |
|------|-------|----------------|
| `climate.py` | 1,879 | God class: AdaptiveThermostat entity |
| `adaptive/learning.py` | 1,659 | AdaptiveLearner: 63 methods, 27 attrs |
| `const.py` | 1,101 | Constants, enums, config dicts, threshold functions |
| `managers/heater_controller.py` | 1,025 | HeaterController: 36 methods, 44 attrs |
| `coordinator.py` | 888 | Coordinator + ModeSync (two classes) |
| `__init__.py` | 863 | Domain setup: 352-line async_setup function |

### Files Over 400 Lines (Should Be Reviewed)

| File | Lines | Notes |
|------|-------|-------|
| `adaptive/physics.py` | 842 | Physics calculations, many heating-type dicts |
| `managers/state_attributes.py` | 794 | Attribute builders, 187-line `_build_status_attribute` |
| `managers/cycle_tracker.py` | 773 | CycleTrackerManager: 38 methods, 43 attrs |
| `pid_controller/__init__.py` | 724 | PID: 36 methods, 46 attrs |
| `sensors/performance.py` | 711 | Performance sensor entities |
| `adaptive/cycle_analysis.py` | 707 | Cycle analysis & metrics |
| `central_controller.py` | 656 | CentralController: 31 methods, 36 attrs |
| `managers/cycle_metrics.py` | 646 | CycleMetricsRecorder: 17 methods, 28 attrs |
| `sensors/energy.py` | 584 | Energy sensor entities |
| `adaptive/heating_rate_learner.py` | 547 | Heating rate learner |
| `services/scheduled.py` | 534 | Scheduled services (weekly report) |
| `adaptive/undershoot_detector.py` | 516 | Undershoot detection |
| `managers/control_output.py` | 505 | Control output manager |
| `managers/pid_tuning.py` | 493 | PID tuning manager |
| `adaptive/pid_rules.py` | 488 | PID rule evaluation |
| `services/__init__.py` | 473 | Service registration handlers |
| `managers/night_setback_calculator.py` | 470 | Night setback calculations |
| `adaptive/ke_learning.py` | 458 | Ke outdoor compensation learning |
| `managers/pwm_controller.py` | 450 | PWM switching logic |
| `climate_setup.py` | 448 | Platform schema & setup |
| `adaptive/thermal_groups.py` | 436 | Thermal group management |
| `managers/status_manager.py` | 432 | Status aggregation |
| `protocols.py` | 429 | Protocol definitions (5+ protocols) |
| `managers/night_setback_manager.py` | 429 | Night setback orchestration |
| `adaptive/thermal_rates.py` | 407 | Thermal rate learning |
| `managers/pid_gains_manager.py` | 404 | PID gains mutation manager |

### Directory Structure

```
custom_components/adaptive_climate/    # 32,282 lines total
  __init__.py                (863)     # Domain setup, service registration, config schema
  climate.py                 (1,879)   # Main entity class (GOD CLASS)
  climate_setup.py           (448)     # Platform schema & async_setup_platform
  climate_init.py            (381)     # Manager initialization factory
  climate_control.py         (377)     # Control loop mixin
  climate_handlers.py        (325)     # Event handler mixin
  const.py                   (1,101)   # All constants, enums, config, thresholds
  coordinator.py             (888)     # Zone registry, ModeSync, outdoor temp EMA
  central_controller.py      (656)     # Central demand aggregation
  protocols.py               (429)     # ThermostatState and sub-protocols
  sensor.py                  (168)     # Sensor platform setup
  number.py                  (92)      # Number entity platform

  adaptive/                  (8,820)   # Learning, physics, detection algorithms
    learning.py              (1,659)   # AdaptiveLearner (core learning engine)
    physics.py               (842)     # Physics-based PID initialization
    cycle_analysis.py        (707)     # Cycle metrics & overshoot tracking
    heating_rate_learner.py  (547)     # Heating rate observation/binning
    undershoot_detector.py   (516)     # Dual-mode undershoot detection
    pid_rules.py             (488)     # Rule-based PID adjustments
    ke_learning.py           (458)     # Outdoor compensation learning
    thermal_groups.py        (436)     # Thermal group feedforward
    thermal_rates.py         (407)     # Thermal rate learning
    validation.py            (396)     # Auto-apply validation manager
    night_setback.py         (390)     # Night setback data model
    preheat.py               (388)     # Preheat prediction learner
    contact_sensors.py       (335)     # Contact sensor detection
    persistence.py           (307)     # LearningDataStore
    learner_serialization.py (292)     # Serialize/deserialize learner state
    confidence.py            (246)     # Convergence confidence tracker
    auto_apply.py            (250)     # Auto-apply safety gates
    confidence_contribution.py (241)   # Confidence contribution caps
    disturbance_detector.py  (240)     # Disturbance rejection
    sun_position.py          (234)     # Solar position calculations
    humidity_detector.py     (220)     # Humidity spike detection
    floor_physics.py         (253)     # Floor construction physics
    vacation.py              (187)     # Vacation mode handler
    robust_stats.py          (185)     # Robust averaging (outlier rejection)
    manifold_registry.py     (180)     # Manifold pipe delay tracking
    cycle_weight.py          (127)     # Cycle weight classification
    pwm_tuning.py            (97)      # PWM tuning utilities

  managers/                  (7,975)   # All manager classes
    heater_controller.py     (1,025)   # Device actuation & PWM
    state_attributes.py      (794)     # HA state attribute builder
    cycle_tracker.py         (773)     # Cycle state machine
    cycle_metrics.py         (646)     # Cycle end analysis
    control_output.py        (505)     # PID output calculation
    pid_tuning.py            (493)     # PID tuning orchestration
    night_setback_calculator.py (470)  # Night setback calc
    pwm_controller.py        (450)     # PWM duty accumulator
    status_manager.py        (432)     # Status aggregation
    night_setback_manager.py (429)     # Night setback orchestration
    pid_gains_manager.py     (404)     # PID gain mutations
    ke_manager.py            (377)     # Ke learning manager
    temperature_manager.py   (343)     # Temp tracking & filtering
    auto_mode_switching.py   (324)     # Auto heat/cool switching
    events.py                (230)     # CycleEventDispatcher & event types
    state_restorer.py        (225)     # State restoration from HA
    setpoint_boost.py        (177)     # Setpoint feedforward
    learning_gate.py         (148)     # Learning pause conditions
    notification_manager.py  (106)     # HA notification wrapper
    learning_milestone.py    (88)      # Learning progress notifications
    heat_pipeline.py         (81)      # Heat delivery pipeline
    comfort_degradation.py   (71)      # Comfort scoring

  sensors/                   (1,955)   # Sensor entity implementations
    performance.py           (711)     # Performance metrics sensors
    energy.py                (584)     # Energy tracking sensors
    comfort.py               (297)     # Comfort score sensor
    actuator_wear.py         (179)     # Actuator wear sensor
    health.py                (145)     # System health sensor

  analytics/                 (974)     # Analytics & reporting
    energy.py                (264)     # Energy analytics
    health.py                (257)     # Health analytics
    history_store.py         (252)     # History storage
    reports.py               (246)     # Weekly report generation
    heat_output.py           (155)     # Heat output analytics

  services/                  (1,007)   # Service handlers
    __init__.py              (473)     # Service registration
    scheduled.py             (534)     # Scheduled tasks

  solar/                     (359)     # Solar gain
    solar_gain.py            (356)     # Solar gain calculation

  helpers/                   (130)     # Utility helpers
    registry.py              (81)      # Entity registry helpers
    hvac_mode.py             (46)      # HVAC mode utils
```

## Module Dependency Graph

### Core Dependencies (heaviest coupling)

```
__init__.py
  -> coordinator, central_controller, adaptive.thermal_groups
  -> adaptive.manifold_registry, adaptive.vacation, services

climate.py
  -> climate_control, climate_handlers, climate_init
  -> adaptive: physics, night_setback, contact_sensors, humidity_detector, ke_learning, preheat
  -> managers: ALL (via managers/__init__.py re-exports)
  -> managers.events, managers.pid_gains_manager, managers.state_attributes, managers.status_manager

climate_init.py -> climate (circular, guarded by TYPE_CHECKING)
climate_control.py -> const, managers.events
climate_handlers.py -> const, managers.events
climate_setup.py -> climate (circular, guarded by TYPE_CHECKING), adaptive.learning, adaptive.persistence

coordinator.py -> central_controller (circular, guarded), adaptive.sun_position, managers.auto_mode_switching
central_controller.py -> coordinator (circular, guarded)
```

### Circular Dependencies (4 cycles, all TYPE_CHECKING guarded)

1. `climate.py` <-> `climate_init.py` -- init factory needs climate type
2. `climate.py` <-> `managers/state_attributes.py` -- attrs builder needs thermostat type
3. `coordinator.py` <-> `managers/auto_mode_switching.py` -- mutual reference
4. `coordinator.py` <-> `central_controller.py` -- mutual reference

These are structurally safe (guarded by `TYPE_CHECKING`) but indicate tightly coupled domains. There are **37 files** using `TYPE_CHECKING` guards throughout the codebase.

### Manager Dependencies on climate.py (via TYPE_CHECKING)

These managers import `AdaptiveThermostat` or `SmartThermostat` under TYPE_CHECKING:
- `managers/heater_controller.py`
- `managers/pwm_controller.py`
- `managers/state_attributes.py`
- `managers/state_restorer.py`
- `managers/temperature_manager.py`
- `managers/ke_manager.py`
- `managers/pid_tuning.py`

This means they reference `self._thermostat` or accept the full thermostat as a parameter, bypassing the Protocol pattern documented in `manager-communication.md`.

## Code Smells

### 1. God Class: AdaptiveThermostat (CRITICAL)

**File:** `climate.py:83` -- 102 methods, 168 `self._` attributes

Despite being split into mixins (`ClimateControlMixin`, `ClimateHandlersMixin`), the class is the gravitational center of the entire system. The `__init__` alone is 376 lines of argument unpacking and initialization.

**Evidence of bloat:**
- `ClimateControlMixin` accesses 49 `self._` attributes from the thermostat
- `ClimateHandlersMixin` accesses 35 `self._` attributes from the thermostat
- Mixin pattern provides no real encapsulation -- they are just code-organization splits

**Refactoring opportunity:** Extract configuration into a dataclass (`ThermostatConfig`), reduce `__init__` to config unpacking + manager delegation.

### 2. Long Methods (40+ lines)

Top offenders:

| Lines | Location | Method |
|-------|----------|--------|
| 376 | `climate.py:86` | `AdaptiveThermostat.__init__` |
| 352 | `__init__.py:406` | `async_setup` |
| 334 | `adaptive/learning.py:514` | `calculate_pid_adjustment` |
| 328 | `climate_init.py:54` | `async_setup_managers` |
| 257 | `managers/pwm_controller.py:194` | `PWMController.async_pwm_switch` |
| 251 | `climate_setup.py:198` | `async_setup_platform` |
| 244 | `managers/cycle_metrics.py:349` | `record_cycle_metrics` |
| 244 | `climate_control.py:27` | `_async_control_heating` |
| 240 | `pid_controller/__init__.py:485` | `PID.calc` |
| 239 | `adaptive/pid_rules.py:162` | `evaluate_pid_rules` |
| 234 | `services/scheduled.py:165` | `_run_weekly_report_core` |
| 187 | `managers/state_attributes.py:608` | `_build_status_attribute` |
| 185 | `managers/control_output.py:121` | `calc_output` |
| 161 | `managers/cycle_tracker.py:57` | `CycleTrackerManager.__init__` |
| 151 | `managers/night_setback_manager.py:222` | `calculate_night_setback_adjustment` |
| 144 | `adaptive/learning.py:1052` | `update_convergence_confidence` |

### 3. God Classes (Beyond AdaptiveThermostat)

| Class | File | Methods | Self Attrs |
|-------|------|---------|------------|
| `AdaptiveThermostat` | `climate.py:83` | 102 | 168 |
| `AdaptiveLearner` | `adaptive/learning.py:119` | 63 | 27 |
| `PID` | `pid_controller/__init__.py:41` | 36 | 46 |
| `CycleTrackerManager` | `managers/cycle_tracker.py:45` | 38 | 43 |
| `AdaptiveThermostatCoordinator` | `coordinator.py:32` | 38 | 25 |
| `HeaterController` | `managers/heater_controller.py:82` | 36 | 44 |
| `ThermostatState` | `protocols.py:176` | 33 | 0 (Protocol) |
| `CentralController` | `central_controller.py:28` | 31 | 36 |

### 4. Duplicated Heating-Type Configuration Dicts

The pattern of `{HeatingType.FLOOR_HYDRONIC: ..., HeatingType.RADIATOR: ..., ...}` dicts appears in **16+ locations** across the codebase:

- `const.py:747` -- main characteristics table
- `pid_controller/__init__.py:15,21,91` -- PID-specific params
- `adaptive/physics.py:337,454,567,588,626,651` -- physics constants
- `adaptive/learning.py:133` -- learner defaults
- `adaptive/night_setback.py:47,126,152` -- setback params
- `adaptive/heating_rate_learner.py:46,70` -- rate learner params

Each duplicates the 4-way heating type switch. Changes to heating type behavior require touching many files.

**Refactoring opportunity:** Consolidate all heating-type-specific constants into a single `HeatingTypeProfile` dataclass in `const.py`, with all per-type parameters in one place.

### 5. Inline Coordinator Access (Style Violation)

CLAUDE.md mandates `self._coordinator` cached property, but `hass.data.get(DOMAIN, {}).get("coordinator")` appears in **9 locations**:
- `climate.py:859`
- `climate_control.py:56,65,329`
- `climate_setup.py:340`
- `managers/night_setback_calculator.py:112`
- `sensors/energy.py:301`
- `sensors/health.py:49`
- `sensors/performance.py:76`

### 6. Mixin Anti-Pattern

`ClimateControlMixin` and `ClimateHandlersMixin` access the parent class's private attributes directly. This is not real separation of concerns -- it is just splitting a file into pieces while maintaining full coupling. The mixins have no independent testability.

### 7. `_build_status_attribute` Creates New StatusManager

At `managers/state_attributes.py:639`, `_build_status_attribute` creates a **new StatusManager** instance on every call instead of using `thermostat._status_manager`. Comment says "for test compatibility" but this duplicates state and wastes cycles.

### 8. Backward-Compatibility Property Aliases

`adaptive/learning.py:195-215` defines multiple backward-compatible aliases for private attributes (`_cycle_history`, `_heating_convergence_confidence`). These exist solely for tests accessing private internals.

### 9. HAS_HOMEASSISTANT Try/Except Import Pattern

`managers/heater_controller.py:10-63` and `__init__.py:11-30` use try/except ImportError blocks with 50+ fallback constant assignments. This is fragile and duplicates HA constants.

## Test Coverage Gaps

### Source Modules Without Dedicated Test Files (10 files, 2,695 lines)

| Module | Lines | Risk |
|--------|-------|------|
| `climate_control.py` | 377 | **HIGH** - Core control loop, only tested indirectly |
| `services/scheduled.py` | 534 | **HIGH** - Weekly reports, daily learning triggers |
| `managers/night_setback_manager.py` | 429 | **HIGH** - Night setback orchestration |
| `protocols.py` | 429 | **MEDIUM** - Protocol definitions, tested via implementors |
| `climate_handlers.py` | 325 | **MEDIUM** - Event handlers, tested via integration tests |
| `adaptive/floor_physics.py` | 253 | **MEDIUM** - Floor thermal calculations |
| `adaptive/disturbance_detector.py` | 240 | **MEDIUM** - Disturbance rejection logic |
| `analytics/heat_output.py` | 155 | **LOW** - Analytics calculations |
| `number.py` | 92 | **LOW** - Simple number entity |
| `helpers/hvac_mode.py` | 46 | **LOW** - Small utility module |

### Coverage Summary

- **Total source modules:** 74 (excluding `__init__.py` files)
- **Modules with tests:** 64 (86%)
- **Modules without tests:** 10 (14%)
- **Untested lines:** ~2,695

## Recent Git History (Last 20 Commits)

### Theme Distribution

| Theme | Count | Description |
|-------|-------|-------------|
| `style:` | 5 | Ruff formatting, typing modernization, lint fixes |
| `docs:` | 4 | CLAUDE.md updates, plan documentation |
| `refactor:` | 3 | Remove migration code, fix pyright errors |
| `chore:` | 3 | Ruff/pyright tooling setup, pre-commit hooks |
| `test:` | 2 | Test updates for v10 format, remove legacy tests |
| `chore(release):` | 2 | Version 0.63.0 and 0.63.1 |
| `fix:` | 1 | Store config values before coordinator init |

### Recent Focus

The last 20 commits show a **tooling and cleanup phase**: adding ruff + pyright, applying formatting, removing migration code, modernizing type annotations. No feature work in this window.

## Top Refactoring Priorities

### Priority 1: `climate.py` God Class Decomposition

**Impact:** High. 1,879 lines, 102 methods, 168 attributes.
**Approach:**
1. Extract `ThermostatConfig` dataclass from `__init__` kwargs unpacking (~200 lines)
2. Move remaining `__init__` initialization to `climate_init.py`
3. Consider extracting state properties into a dedicated `ThermostatStateImpl` class
4. Move `_setup_state_listeners` to `climate_handlers.py`
5. Move `async_will_remove_from_hass` cleanup to a dedicated teardown module

### Priority 2: Heating-Type Config Consolidation

**Impact:** Medium-High. 16+ scattered dicts.
**Approach:**
1. Create `HeatingTypeProfile` dataclass in `const.py` containing ALL per-type params
2. Single `HEATING_TYPE_PROFILES: dict[HeatingType, HeatingTypeProfile]` lookup
3. Update all 16+ consumers to reference the unified profile

### Priority 3: `adaptive/learning.py` Decomposition

**Impact:** Medium-High. 1,659 lines, 63 methods.
**Approach:**
1. Already partially decomposed (confidence, validation, auto_apply, cycle_weight extracted)
2. `calculate_pid_adjustment` (334 lines) could delegate more to `pid_rules.py`
3. `update_convergence_confidence` (144 lines) could move to `confidence.py`
4. Backward-compatibility aliases should be removed (update tests instead)

### Priority 4: `__init__.py` `async_setup` Split

**Impact:** Medium. 352-line setup function + 104-line unload.
**Approach:**
1. Extract service registration to `services/__init__.py` (already partially there)
2. Extract config schema validation to a dedicated module
3. Extract coordinator/controller creation to factory functions

### Priority 5: Protocol Adoption Completion

**Impact:** Medium. 7 managers still use full thermostat reference.
**Approach:**
1. Migrate `HeaterController`, `PWMController`, `StateRestorer`, `TemperatureManager` to use sub-protocols
2. Eliminate direct `AdaptiveThermostat` imports in managers
3. Fix `_build_status_attribute` to use existing `_status_manager` instead of creating new one

### Priority 6: Test Coverage for Core Control Path

**Impact:** Medium. `climate_control.py` (377 lines) has no dedicated tests.
**Approach:**
1. Create `test_climate_control.py` testing `_async_control_heating` paths
2. Create `test_night_setback_manager.py` for orchestration logic
3. Create `test_scheduled_services.py` for weekly report/daily learning

## Gotchas

1. **Mixin methods assume full thermostat context** -- `ClimateControlMixin._async_control_heating` references 49 `self._` attributes. Cannot be tested or used independently.

2. **`_build_status_attribute` re-creates StatusManager** every call (`state_attributes.py:639`). This was done "for test compatibility" but is wasteful and can produce inconsistent state if the re-created manager diverges from the real one.

3. **`heater_controller.py` try/except ImportError** block (lines 10-63) defines 15+ fallback constants. If HA API changes, the fallbacks silently provide wrong values.

4. **`adaptive/learning.py` backward-compat aliases** (lines 195-215) let tests access private attributes through multiple paths. This makes refactoring the internal structure risky without first updating all test references.

5. **`coordinator.py` contains two classes** -- `AdaptiveThermostatCoordinator` (38 methods) and `ModeSync` (separate class at end of file). The `ModeSync.on_mode_change` method alone is 93 lines.

6. **9 inline coordinator access violations** exist despite the CLAUDE.md rule mandating `self._coordinator` cached property.
