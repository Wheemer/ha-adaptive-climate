# Code Review Findings

Date: 2026-05-25

Scope: current working tree changes in `custom_components/adaptive_climate` and affected tests.

## Findings

### High: negative HEAT output no longer resets PWM duty accumulator

File: `custom_components/adaptive_climate/managers/pwm_controller.py:233`

The guard changed from `control_output <= 0` to `abs(control_output) == 0`. This treats a negative HEAT output such as `-5` as real positive demand after `abs(control_output)` is used later in PWM math, leaving any existing duty accumulator intact and potentially firing an unwanted heat pulse.

This is also covered by the failing full-suite test:

`tests/test_integration_duty_accumulator.py::TestAccumulatorEdgeCases::test_accumulator_negative_output_resets`

### High: auto mode switching can turn OFF zones back on

File: `custom_components/adaptive_climate/coordinator.py:647`

`_apply_house_mode()` decides whether a zone is non-OFF from `zone["hvac_mode"]`, but production zone data registered in `custom_components/adaptive_climate/climate_setup.py:359` does not include that key. A missing key evaluates as non-OFF, and the changed service call now targets the real `climate_entity_id`, so auto mode switching can call `climate.set_hvac_mode` on zones that are actually OFF.

The updated test masks this by injecting `hvac_mode` into test zone data at `tests/test_coordinator.py:737`.

### High: `forecast_hours` was renamed without compatibility

Files:

- `custom_components/adaptive_climate/__init__.py:205`
- `custom_components/adaptive_climate/const.py:1093`
- `README.md:104`

The config option changed from `forecast_hours` to `forecast_days` without accepting the old key or migrating it. Existing YAML configs using the documented `forecast_hours` option will fail validation in Home Assistant.

### Medium: auto mode switching now hard-depends on forecast service

File: `custom_components/adaptive_climate/managers/auto_mode_switching.py:201`

`async_evaluate()` now requires a successful `weather.get_forecasts` response before any switch. A weather entity with current temperature but no daily forecast support, or a transient forecast-service failure, disables auto mode switching entirely. The previous behavior could still switch from `coordinator.outdoor_temp`.

### Medium: `forecast_days` config is ignored

Files:

- `custom_components/adaptive_climate/managers/auto_mode_switching.py:51`
- `custom_components/adaptive_climate/managers/auto_mode_switching.py:162`
- `tests/test_auto_mode_switching.py:249`

`_forecast_days` is read from config but median calculation always uses `forecast[:7]`. The test now asserts the stale seven-entry behavior even though the default fixture sets `CONF_FORECAST_DAYS: 3`.

### Medium: season-lock tests no longer cover lock branches

Files:

- `tests/test_auto_mode_switching.py:498`
- `tests/test_auto_mode_switching.py:528`
- `custom_components/adaptive_climate/managers/auto_mode_switching.py:237`
- `custom_components/adaptive_climate/managers/auto_mode_switching.py:240`

The winter and summer tests assert allowed switches: HEAT in winter and COOL in summer. They no longer force a forbidden target mode, so regressions in the actual blocking branches can pass.

### Low/Medium: HEAT/COOL integral reset leaves exposed integral stale

Files:

- `custom_components/adaptive_climate/climate.py:1118`
- `custom_components/adaptive_climate/managers/state_attributes.py:56`

HEAT/COOL switching resets `self._pid_controller.integral` but does not update `self._i`. State attributes expose and restore `integral` from `self._i`, so if the next control pass is skipped, Home Assistant can persist and later restore the stale integral value.

## Verification

- `python3 -m ruff check .`: passed.
- `python3 -m pyright`: passed.
- `python3 -m pytest -q`: failed 1 test, `TestAccumulatorEdgeCases.test_accumulator_negative_output_resets`.
- Targeted changed-area run failed on the same test: `1 failed, 110 passed`.
