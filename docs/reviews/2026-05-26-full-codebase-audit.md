# Full Codebase Audit - 2026-05-26

Scope: current working tree under `custom_components/adaptive_climate/` plus the test suite and user-facing docs where they affect runtime behavior.

Validation baseline from this audit pass:

- `python3 -m ruff check .` - passed
- `python3 -m pyright` - passed
- `python3 -m pytest -q` - `2776 passed, 11 skipped, 1 warning`

This audit supersedes the narrower diff review in `docs/reviews/2026-05-25-code-review.md` for current-tree findings.

## High Severity

### H01 - Climate entities can silently get PWM despite validation saying valve mode

`validate_pwm_compatibility()` only rejects climate heater/cooler entities when `CONF_PWM` is present and non-zero in the zone config (`custom_components/adaptive_climate/climate_setup.py:166`). The setup parameters then use `config.get(CONF_PWM) or domain pwm or DEFAULT_PWM` (`custom_components/adaptive_climate/climate_setup.py:293`), so both omitted PWM and an explicit zero-valued PWM fall through to the 15 minute default. README and tests describe `pwm: 0` / no PWM as direct valve mode (`README.md:216`, `tests/test_climate_setup.py:80`), but the real setup path can create nested PWM around a climate entity.

Fix: treat `None` distinctly from zero-valued timedeltas and run compatibility validation against the effective PWM value after domain defaults are resolved. Add an integration test that constructs parameters through `async_setup_platform`, not an inlined validator.

### H02 - Signed heat/cool output is still treated as demand outside the PWM controller

`PWMController` now treats HEAT negative and COOL positive outputs as no-demand (`custom_components/adaptive_climate/managers/pwm_controller.py:230`), but `HeaterController` still derives demand and action from `abs(control_output)` (`custom_components/adaptive_climate/managers/heater_controller.py:1014`, `:1070`, `:1086`, `:1111`). A concrete COOL path is sensor stall: `_output_safety` is assigned as a positive value (`custom_components/adaptive_climate/climate_control.py:131`), then valve mode sends `abs(control_output)` to the cooler valve. That opens cooling output on a safety fallback instead of failing closed.

Fix: centralize a mode-aware `has_demand/control_magnitude` helper and use it for demand tracking, full-duty checks, PWM delegation, and valve value writes. Add COOL tests with positive output in both PWM and valve modes.

### H03 - AC zones starting in HEAT initialize PID with COOL-only output limits

When any cooler exists, `_ac_mode` sets the PID output range to negative cooling values (`custom_components/adaptive_climate/climate.py:170`). That happens before considering `initial_hvac_mode` (`custom_components/adaptive_climate/climate.py:105`) and before constructing the PID (`custom_components/adaptive_climate/climate.py:441`). A fresh AC-capable entity configured with `initial_hvac_mode: heat` starts with a HEAT mode but a cooling-signed output range, then immediately runs control on startup (`custom_components/adaptive_climate/climate.py:548`).

Fix: make PID output bounds mode-specific at initialization and on mode changes. Add a startup test for an AC-capable zone with `initial_hvac_mode: heat`.

### H04 - Dynamic manifold delay lookups use zone slugs while configured manifolds use climate entity IDs

Manifold config requires climate entity IDs (`custom_components/adaptive_climate/__init__.py:191`) and the registry indexes those values directly (`custom_components/adaptive_climate/adaptive/manifold_registry.py:65`). Runtime lookups still pass zone slugs in the PWM/control path (`custom_components/adaptive_climate/climate_control.py:343`) and night-setback preheat path (`custom_components/adaptive_climate/climate_init.py:154`). Those lookups miss the registry and return zero delay (`custom_components/adaptive_climate/adaptive/manifold_registry.py:115`).

Fix: standardize coordinator manifold APIs on entity IDs, or normalize inside the coordinator before registry calls. Cover PWM effective on-time and night-setback preheat with a real manifold config.

### H05 - The first cold-manifold cycle can lose its transport delay permanently

`set_control_value()` queries transport delay before `climate_control.py` updates zone demand (`custom_components/adaptive_climate/climate_control.py:341`, `:288`, `:292`). The coordinator builds active loops only from `_demand_states` (`custom_components/adaptive_climate/coordinator.py:148`), so the initiating zone is absent. The registry returns zero when no active loops exist (`custom_components/adaptive_climate/adaptive/manifold_registry.py:133`). The subsequent heating-start handler marks the manifold warm (`custom_components/adaptive_climate/climate.py:1865`), so the missing first-cycle delay is not recovered.

Fix: include the requesting zone in the active-zone calculation before querying, or update demand before actuator control. Add a cold-manifold first-cycle test.

### H06 - Heat-output sensor configuration is accepted but never passed to zone sensors

Domain setup stores `supply_temp_sensor`, `return_temp_sensor`, `flow_rate_sensor`, and fallback flow in `hass.data` (`custom_components/adaptive_climate/__init__.py:622`). `sensor.py` reads those values only from `discovery_info` (`custom_components/adaptive_climate/sensor.py:66`), but the discovery payload omits them (`custom_components/adaptive_climate/climate_setup.py:385`). Configured heat-output sensors therefore remain unused and `HeatOutputSensor` falls back to missing inputs/default flow.

Fix: add those keys to the sensor discovery payload or have `sensor.py` read domain data directly. Add a setup test that verifies `HeatOutputSensor` receives configured entities.

### H07 - PID rollback calls an API that AdaptiveLearner no longer implements

`PIDTuningManager.async_rollback_pid()` calls `adaptive_learner.get_previous_pid()` (`custom_components/adaptive_climate/managers/pid_tuning.py:410`), but the production `AdaptiveLearner` no longer defines that method (`rg get_previous_pid` only finds docs/tests and the caller). The rollback service and validation-failure rollback path therefore fail in production; the unit test masks this with a `MagicMock` method (`tests/test_pid_tuning_manager.py:444`).

Fix: move rollback source-of-truth to `PIDGainsManager` history, or restore a real `AdaptiveLearner.get_previous_pid()` implementation that delegates there. Add a test with a real learner and gains manager.

### H08 - Cooling cycles are saved and learned as heating cycles

`CycleMetricsManager` computes a `mode` field and stores it in the `CycleMetrics` object (`custom_components/adaptive_climate/managers/cycle_metrics.py:512`, `:548`), but it calls learner APIs without passing that mode (`custom_components/adaptive_climate/managers/cycle_metrics.py:554`). `AdaptiveLearner.add_cycle_metrics()` and `update_convergence_confidence()` default missing mode to HEAT (`custom_components/adaptive_climate/adaptive/learning.py:392`, `:1103`). Cooling history, confidence, and recommendations are polluted into the heating side.

Fix: route `metrics.mode` through `add_cycle_metrics`, convergence tracking, and confidence updates. Add an end-to-end COOL cycle finalization test that asserts cooling history increments and heating history does not.

### H09 - Heating-rate sessions never receive real cycle duty data

The heating-rate session handler only calls `update_session()` when `event.metrics["duty"]` exists (`custom_components/adaptive_climate/climate.py:1490`). `CycleMetricsManager` builds the `CYCLE_ENDED` metrics dict without a duty field (`custom_components/adaptive_climate/managers/cycle_metrics.py:609`). Since `HeatingRateLearner.update_session()` is the only path that increments `cycles_in_session` and duty history (`custom_components/adaptive_climate/adaptive/heating_rate_learner.py:304`), stall and low-duty logic is effectively unwired.

Fix: include effective duty in `CycleMetrics` / `CycleEndedEvent`, or derive it in the handler from the heater controller. Add a test that a real completed cycle increments `cycles_in_session`.

### H10 - Cooling compressor protection is not applied from `cooling_type`

Cooling characteristics define compressor min-cycle defaults (`custom_components/adaptive_climate/const.py:286`), and `HeaterController` accepts `cooling_type` (`custom_components/adaptive_climate/managers/heater_controller.py:102`), but `async_setup_managers()` never passes it (`custom_components/adaptive_climate/climate_init.py:80`). The turn-off guard only enforces `effective_min_open_time` (`custom_components/adaptive_climate/managers/heater_controller.py:813`), while setup defaults `min_open_time` to zero unless manually configured (`custom_components/adaptive_climate/climate_setup.py:263`).

Fix: pass cooling type into the controller and derive mode-specific min cycle defaults when users do not override them. Test forced-air/mini-split defaults through the real setup path.

## Medium Severity

### M01 - Manifold warm/cold state is saved on unload but not restored on normal startup

`async_setup()` attempts manifold restore before `learning_store` exists (`custom_components/adaptive_climate/__init__.py:593`), while the store is created later by climate platform setup (`custom_components/adaptive_climate/climate_setup.py:210`). Unload saves manifold state (`custom_components/adaptive_climate/__init__.py:832`), but the normal startup path usually skips restore, so manifolds restart cold/warm state from scratch.

Fix: create/load `LearningDataStore` before manifold registry restore, or defer registry restore until platform setup has created the store.

### M02 - The documented learning-window number entity is never loaded

`number.py` defines `LearningWindowNumber` (`custom_components/adaptive_climate/number.py:23`) and README documents `number.adaptive_climate_learning_window` (`README.md:273`). The YAML setup path only explicitly discovers sensors from `climate_setup.py` (`custom_components/adaptive_climate/climate_setup.py:385`). `PLATFORMS` includes `"number"` (`custom_components/adaptive_climate/__init__.py:131`) but there is no config-entry forwarding or YAML discovery path that instantiates it.

Fix: load the number platform during domain setup or sensor/number discovery, and add a test that the entity is created.

### M03 - SystemHealthSensor is defined but never added, so weekly reports default to healthy

`SystemHealthSensor` exists (`custom_components/adaptive_climate/sensors/health.py:20`) and `sensor.py` imports it, but the sensor list never appends it (`custom_components/adaptive_climate/sensor.py:75`, `:122`). Weekly reports read `sensor.heating_system_health` (`custom_components/adaptive_climate/services/scheduled.py:358`) and otherwise keep the default `"healthy"` (`custom_components/adaptive_climate/analytics/reports.py:91`).

Fix: add one system health sensor with the other system-wide sensors, or compute health directly in the weekly report.

### M04 - `forecast_hours` alias is accepted but shadowed by the `forecast_days` default

The schema injects `forecast_days` with a default (`custom_components/adaptive_climate/__init__.py:205`) while also accepting legacy `forecast_hours` (`custom_components/adaptive_climate/__init__.py:209`). The manager gives `forecast_days` precedence (`custom_components/adaptive_climate/managers/auto_mode_switching.py:51`), so a YAML config with only `forecast_hours` still uses the default forecast-days value. README still shows `forecast_hours` (`README.md:104`).

Fix: normalize the alias in schema post-processing, or only default `forecast_days` after checking whether `forecast_hours` was provided. Add a schema-level alias test.

### M05 - `contact_action: none` and `frost_protection` are not honored end-to-end

The constants allow `none` (`custom_components/adaptive_climate/const.py:761`), but entity initialization maps every non-`pause` value to `FROST_PROTECTION` (`custom_components/adaptive_climate/climate.py:251`). In COOL, frost protection is converted to pause (`custom_components/adaptive_climate/adaptive/contact_sensors.py:156`) and `StatusManager.is_paused()` enforces pause (`custom_components/adaptive_climate/managers/status_manager.py:175`). In HEAT, the main control loop only checks pause state (`custom_components/adaptive_climate/climate_control.py:67`) and never applies the adjusted frost-protection setpoint helper.

Fix: represent `none` as its own enum value, and wire frost protection into the target setpoint path rather than only the pause path.

### M06 - Humidity pause integral decay compounds from a stale baseline

During humidity pauses, the control loop calculates elapsed time from `_last_control_time` and decays integral (`custom_components/adaptive_climate/climate_control.py:105`), then returns without updating `_last_control_time` (`custom_components/adaptive_climate/climate_control.py:124`). `_last_control_time` is refreshed only after normal control. Multiple humidity updates during one pause repeatedly apply decay for the full elapsed period.

Fix: update the decay baseline after applying pause decay, or track a separate humidity-pause decay timestamp.

### M07 - Ke observations are not persisted during normal operation

`KeManager` appends observations in normal flow (`custom_components/adaptive_climate/managers/ke_manager.py:303`), and `KeLearner.to_dict()` serializes them (`custom_components/adaptive_climate/adaptive/ke_learning.py:415`). The cycle save path writes only `adaptive_data` (`custom_components/adaptive_climate/managers/cycle_metrics.py:358`). `ke_data` is saved only on entity removal (`custom_components/adaptive_climate/climate.py:658`). A restart before removal loses normal Ke observations.

Fix: schedule `ke_data` saves after Ke observations or include the Ke learner in the periodic learning save path.

### M08 - Heating-rate learner mutations after `CYCLE_ENDED` are saved too early or not at all

`CycleMetricsManager` schedules the learning save before emitting `CYCLE_ENDED` (`custom_components/adaptive_climate/managers/cycle_metrics.py:594`, `:597`). The heating-rate handler then mutates the learner after the scheduled snapshot (`custom_components/adaptive_climate/climate.py:1457`, `:1501`) but does not update/schedule `LearningDataStore`. End-session observations can be missing from persistence until a later unrelated save.

Fix: emit cycle events before snapshotting adaptive learner data, or have heating-rate handlers schedule their own save like preheat does (`custom_components/adaptive_climate/climate.py:1449`).

### M09 - Small PID changes can apply to the controller but disappear from PID history

`PIDGainsManager.set_gains()` syncs new gains to the controller first (`custom_components/adaptive_climate/managers/pid_gains_manager.py:161`) and records history only if rounded values differ (`custom_components/adaptive_climate/managers/pid_gains_manager.py:164`). The dedupe helper rounds Ki and Ke to two decimals (`custom_components/adaptive_climate/managers/pid_gains_manager.py:103`), while state serialization keeps Ki to four decimals (`custom_components/adaptive_climate/managers/state_attributes.py:72`). Small but meaningful Ki changes can be active without any audit trail.

Fix: dedupe on full stored precision, or record every explicit gain change with a reason.

### M10 - Cooling PID history is not exposed in state attributes, so restore remains lossy

State attributes call `get_history()` without a mode (`custom_components/adaptive_climate/managers/state_attributes.py:65`), which defaults to heating history (`custom_components/adaptive_climate/managers/pid_gains_manager.py:219`). Flat restored history is treated as heating (`custom_components/adaptive_climate/managers/pid_gains_manager.py:286`). Although `PIDGainsManager` can restore mode-keyed dicts, the entity never writes them that way, so cooling PID history does not survive a normal state round trip.

Fix: persist PID history as `{"heating": [...], "cooling": [...]}` and add a restore round-trip test with cooling entries.

### M11 - State attribute reads launch background milestone tasks

`build_state_attributes()` creates a background task for milestone checks while building attributes (`custom_components/adaptive_climate/managers/state_attributes.py:289`). HA may read attributes often for state writes, UI, recorder, or templates; this makes a read path mutate system behavior and can enqueue duplicate milestone checks.

Fix: move milestone checks to cycle completion or confidence-change events, and keep state attribute generation pure.

## Low Severity / Documentation Drift

### L01 - README lists `adaptive_climate.cost_report`, but no such service is declared or registered

README documents `adaptive_climate.cost_report` (`README.md:292`). `services.yaml` declares the public domain services from `run_learning` through `set_vacation_mode` and does not include `cost_report` (`custom_components/adaptive_climate/services.yaml:117`). Runtime registration also only registers vacation, weekly report, run learning, and recommendations (`custom_components/adaptive_climate/services/__init__.py:404`).

Fix: remove the README entry or implement/register the service.

### L02 - Some tests verify copied or mocked behavior instead of production paths

Examples: `tests/test_pwm_climate_validation.py` inlines a copy of `validate_pwm_compatibility()` instead of importing production code, and `tests/test_pid_tuning_manager.py:444` mocks `get_previous_pid()` even though production `AdaptiveLearner` lacks that method. This lets important integration bugs pass while unit checks stay green.

Fix: replace copied validators and fully mocked collaborators with focused integration tests for setup, rollback, and persistence boundaries.

## Suggested Remediation Order

1. Fix H01/H02/H03 together as a mode/sign contract pass for output handling.
2. Fix H04/H05/M01 as one manifold transport-delay lifecycle pass.
3. Fix H07, then add real rollback validation tests.
4. Fix H08/H09/M07/M08 as a learning event/persistence pass.
5. Fix H06/M02/M03 sensor/platform loading.
6. Address M04/M05 and README drift before release notes or user-facing docs are updated.
