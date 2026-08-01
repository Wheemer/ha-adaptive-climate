# Water Temperature Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drive the heat pump's cooling- and heating-supply water temperature setpoints from Adaptive Climate — cooling from a condensation-safe indoor dew point, heating from a configured target — with multi-day ramps on seasonal resume, learning suppression while ramping, and unification of the existing static cooling-setpoint clamp.

**Architecture:** A pure `dew_point()` helper (`helpers/dew_point.py`) feeds a stateless-per-cycle source scanner (`managers/water_temp_sources.py`) that walks COOL-mode zones plus configured extra sensor pairs and returns the worst (highest) dew point with per-source smoothing and guards. A `WaterTempController` (`managers/water_temp_controller.py`) turns that scan into an effective supply temperature per mode, applies ramp/interlock/write policy, and pushes values to external `number`/`input_number` entities via HA service calls. The controller is owned by the coordinator (constructed in `coordinator.__init__` from the domain config dict, torn down in `async_cleanup()`), persists its ramp/write state through the existing `LearningDataStore` as an additive top-level key, and exposes a learning gate that zones consult to suppress cycle recording and undershoot detection while the water temperature is moving.

**Tech Stack:** Python 3.12+, Home Assistant custom component, voluptuous config schemas, pytest, ruff, pyright (strict on source).

## Global Constraints

Every task's requirements implicitly include this section.

- **TDD ordering per task:** write the failing test → run it and confirm it fails → write the minimal implementation → run and confirm it passes → commit.
- **Max 5 files per task.** If a step would push a task past 5 files, stop and report — do not merge tasks.
- **Never run tests or typechecks directly** — delegate every `pytest` / `pyright` / `ruff` run to a **test-runner** subagent. Steps are written as `Run: pytest ...` anyway; hand the command to test-runner.
- **No `assert` in production code** — raise `ValueError` / `TypeError`. `assert` is fine in tests.
- **PEP 604 unions:** `X | None`, never `Optional[X]`.
- **Timestamps:** `homeassistant.util.dt.utcnow()` for wall-clock. Never `datetime.now()`, never `time.time()`. **Never `time.monotonic()` for anything persisted** — all water-temp state uses `dt_util.utcnow()` and is serialized as ISO 8601.
- **`@callback` only on synchronous functions** — never on `async def`.
- **Max 800 lines per file.** `coordinator.py` (1138), `__init__.py` (872), `climate.py` (1243), `const.py` (1140), `state_attributes.py` (826) are already over — keep additions to those files minimal (properties, constants, small hooks). New logic goes in the new modules.
- **Ruff:** line-length 120, import sorting, pyupgrade. **Pyright:** strict on `custom_components/`, excluded from `tests/`.
- **Type ignores:** `# type: ignore[specific-code]` with an explanatory comment, only at HA boundaries. Never bare `# type: ignore`.
- **Persistence:** HA Store API only, via `LearningDataStore`. No new `Store` instances, no file-based saves. **No `STORAGE_VERSION` bump** — it stays at 5; `_validate_data` only requires `version` and `zones`, so an extra top-level key is additive.
- **Coordinator access from entities:** use the `self._coordinator` cached property — never inline `hass.data.get(DOMAIN, {}).get("coordinator")`.
- **Entity IDs:** use `split_entity_id()` — never string slicing.
- **Commit messages:** Angular conventions, `feat:` / `fix:` / `test:` / `docs:` with an optional one-word scope.
- **Spec defaults are user-approved and must be used verbatim:** `dew_point_margin: 2.0`, `cooling.ramp_rate: 1.0`, `heating.ramp_rate: 2.0`, `idle_days: 7`, `min_write_interval: 1800`, `min_supply_temp: 18.0`, `fallback_humidity: 65`, `cooling.ramp_start: 22.0`, `heating.ramp_start: 25.0`.

## File Structure

**Create:**

| File | Responsibility |
|------|----------------|
| `custom_components/adaptive_climate/helpers/dew_point.py` | Pure Magnus-Tetens `dew_point(temp_c, rh_pct) -> float`. No HA imports. |
| `custom_components/adaptive_climate/managers/water_temp_sources.py` | `DewPointScanner` — enumerate sources, pair temps, smooth RH, apply plausibility/staleness/blind guards, return `DewPointScan`. |
| `custom_components/adaptive_climate/managers/water_temp_controller.py` | `WaterTempController` — targets, ramps, write policy, interlocks, timers, persistence state, learning gate, diagnostics. |
| `custom_components/adaptive_climate/sensors/water_temp.py` | `WaterTempSupplySensor` — one system-wide diagnostic sensor. |
| `tests/test_dew_point.py` | Reference points + `ValueError` boundaries. |
| `tests/test_water_temp_config.py` | Schema + cross-key validation. |
| `tests/test_water_temp_sources.py` | Source selection, exclusions, pairing, guards. |
| `tests/test_water_temp_controller.py` | Targets, ramps, write policy, interlocks, gate. |
| `tests/test_water_temp_persistence.py` | Store round-trip + restore guards. |
| `tests/test_water_temp_wiring.py` | Coordinator construction/cleanup, zone-mode helper, save-on-stop/unload. |
| `tests/test_water_temp_learning_gate.py` | Learning suppression across thermostat + pause detector. |
| `tests/test_water_temp_clamp.py` | `min_cooling_target` unification. |
| `tests/test_water_temp_sensor.py` | Diagnostic sensor state + attributes. |

**Modify:**

| File | Change |
|------|--------|
| `const.py` | `CONF_WATER_TEMP_*`, `CONF_EXCLUDE_FROM_DEW_POINT`, defaults and tuning constants. |
| `__init__.py` | `WATER_TEMP_*_SCHEMA` above `CONFIG_SCHEMA`, `validate_water_temp_control` wrapper, no-HA stub branch, static-clamp setup warning, save water-temp state on stop + unload. |
| `coordinator.py` | Construct/own `WaterTempController`, `get_zones_in_mode`, `get_zone_current_temp`, `water_temp_learning_gate`, `effective_cooling_supply_temp`, `min_cooling_target`, teardown in `async_cleanup`. |
| `climate_setup.py` | `exclude_from_dew_point` in `PLATFORM_SCHEMA`, `humidity_sensor` + `exclude_from_dew_point` in `register_zone` zone_data, restore water-temp state next to manifold restore. |
| `climate.py` | `water_temp_learning_gate_active` property, fold into `in_learning_grace_period`, clamp display uses `effective_cooling_supply_temp`. |
| `climate_control.py` | Skip undershoot-detector updates while the water-temp gate is active. |
| `managers/pause_detector.py` | `water_temp_gate` flag in `is_learning_paused()`. |
| `managers/state_attributes.py` | Surface the gate as the existing `learning_grace` override. |
| `adaptive/persistence.py` | `async_load_water_temp_state` / `async_save_water_temp_state`. |
| `sensor.py` | Create `WaterTempSupplySensor` in the system-wide sensor block. |
| `CLAUDE.md` | Architecture table + tests list. |

**Design decisions locked in here (do not re-litigate mid-task):**

1. **Humidity-paused zones are detected via the climate entity's `status` attribute**, not by reaching into `thermostat._humidity_detector`. The scanner skips a zone when its `status.overrides` contains an entry with `type == "humidity"`. Same mechanism as the `open_window` / `contact_open` interlock check. This keeps the controller reading only `hass.states`, with zero new coupling to entity internals.
2. **Implausible RH → fall back to `fallback_humidity` for that source. Implausible or missing *temperature* → skip the source entirely**, because a dew point cannot be computed without a temperature. The spec lumps both under "implausible"; this is the resolution.
3. **The learning-gate settling window is a fixed `WATER_TEMP_SETTLING_MINUTES = 60`** (the slowest heating type's settling window) rather than a per-zone lookup — the water temperature is a house-wide quantity, so the most conservative window applies.
4. **`diagnostics()["mode"]` prefers `"cooling"`** when both modes are somehow active, because cooling is the safety-critical half.

---

### Task 1: Dew point helper

**Files:**
- Create: `custom_components/adaptive_climate/helpers/dew_point.py`
- Test: `tests/test_dew_point.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `dew_point(temp_c: float, rh_pct: float) -> float` — Magnus-Tetens dew point in °C. Raises `ValueError` when `rh_pct <= 0` or `rh_pct > 100`. Module constants `MAGNUS_B = 17.62`, `MAGNUS_C = 243.12`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_dew_point.py`:

```python
"""Tests for the pure Magnus-Tetens dew point helper."""

from __future__ import annotations

import pytest

from custom_components.adaptive_climate.helpers.dew_point import (
    MAGNUS_B,
    MAGNUS_C,
    dew_point,
)


def test_reference_point_25c_60pct():
    """25 degC / 60% RH -> 16.69 degC (spec reference point)."""
    assert dew_point(25.0, 60.0) == pytest.approx(16.69, abs=0.01)


def test_reference_point_20c_50pct():
    """20 degC / 50% RH -> 9.3 degC (spec reference point)."""
    assert dew_point(20.0, 50.0) == pytest.approx(9.3, abs=0.1)


def test_reference_point_30c_80pct():
    """30 degC / 80% RH -> 26.2 degC (spec reference point)."""
    assert dew_point(30.0, 80.0) == pytest.approx(26.2, abs=0.1)


def test_saturation_returns_air_temperature():
    """At 100% RH the dew point equals the air temperature."""
    assert dew_point(21.5, 100.0) == pytest.approx(21.5, abs=0.01)


def test_dew_point_is_monotonic_in_humidity():
    """Higher RH at fixed temperature always yields a higher dew point."""
    assert dew_point(24.0, 40.0) < dew_point(24.0, 55.0) < dew_point(24.0, 70.0)


def test_rh_zero_raises_value_error():
    """RH of 0 is outside the valid (0, 100] domain."""
    with pytest.raises(ValueError, match="Relative humidity"):
        dew_point(22.0, 0.0)


def test_rh_negative_raises_value_error():
    """Negative RH is outside the valid (0, 100] domain."""
    with pytest.raises(ValueError, match="Relative humidity"):
        dew_point(22.0, -5.0)


def test_rh_above_100_raises_value_error():
    """RH above 100 is outside the valid (0, 100] domain."""
    with pytest.raises(ValueError, match="Relative humidity"):
        dew_point(22.0, 101.0)


def test_magnus_coefficients_are_the_specified_ones():
    """The spec pins b=17.62 and c=243.12."""
    assert MAGNUS_B == 17.62
    assert MAGNUS_C == 243.12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dew_point.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'custom_components.adaptive_climate.helpers.dew_point'`

- [ ] **Step 3: Write minimal implementation**

Create `custom_components/adaptive_climate/helpers/dew_point.py`:

```python
"""Pure dew-point math (Magnus-Tetens).

Stateless helper with no Home Assistant imports so it can be unit-tested and
reused anywhere.  Lives under ``helpers/`` rather than ``adaptive/`` because
``adaptive/`` is reserved for learning and physics state.
"""

from __future__ import annotations

import math

# Magnus-Tetens coefficients (Sonntag 1990 set, valid roughly 0-60 degC).
MAGNUS_B = 17.62
MAGNUS_C = 243.12


def dew_point(temp_c: float, rh_pct: float) -> float:
    """Return the dew point in degC for an air temperature and relative humidity.

    Args:
        temp_c: Air temperature in degrees Celsius.
        rh_pct: Relative humidity in percent, in the half-open range (0, 100].

    Returns:
        Dew point temperature in degrees Celsius.

    Raises:
        ValueError: If ``rh_pct`` is <= 0 or > 100.  Project rules forbid
            ``assert`` in production code, so this is an explicit raise.
    """
    if rh_pct <= 0.0 or rh_pct > 100.0:
        raise ValueError(f"Relative humidity must be in the range (0, 100], got {rh_pct}")

    gamma = math.log(rh_pct / 100.0) + (MAGNUS_B * temp_c) / (MAGNUS_C + temp_c)
    return (MAGNUS_C * gamma) / (MAGNUS_B - gamma)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dew_point.py -v`
Expected: PASS — 9 passed

- [ ] **Step 5: Lint and typecheck**

Run: `ruff check custom_components/adaptive_climate/helpers/dew_point.py tests/test_dew_point.py && ruff format --check custom_components/adaptive_climate/helpers/dew_point.py && pyright custom_components/adaptive_climate/helpers/dew_point.py`
Expected: no findings

- [ ] **Step 6: Commit**

```bash
git add custom_components/adaptive_climate/helpers/dew_point.py tests/test_dew_point.py
git commit -m "feat(dewpoint): add pure Magnus-Tetens dew point helper"
```

---

### Task 2: Constants, config schema and cross-key validation

**Files:**
- Modify: `custom_components/adaptive_climate/const.py` (append a new section at end of file)
- Modify: `custom_components/adaptive_climate/__init__.py:170-318`
- Test: `tests/test_water_temp_config.py`

**Interfaces:**
- Consumes: existing `CONF_SUPPLY_TEMPERATURE` (`const.py:695`), `SUPPLY_TEMP_MIN = 25.0` / `SUPPLY_TEMP_MAX = 80.0` (`const.py:698-699`).
- Produces:
  - Config keys: `CONF_WATER_TEMP_CONTROL = "water_temp_control"`, `CONF_WATER_TEMP_IDLE_DAYS`, `CONF_WATER_TEMP_MIN_WRITE_INTERVAL`, `CONF_WATER_TEMP_CONDENSATION_SENSOR`, `CONF_WATER_TEMP_COOLING`, `CONF_WATER_TEMP_HEATING`, `CONF_WATER_TEMP_TARGET_ENTITY`, `CONF_WATER_TEMP_MIN_SUPPLY_TEMP`, `CONF_WATER_TEMP_DEW_POINT_MARGIN`, `CONF_WATER_TEMP_FALLBACK_HUMIDITY`, `CONF_WATER_TEMP_RAMP_START`, `CONF_WATER_TEMP_RAMP_RATE`, `CONF_WATER_TEMP_EXTRA_SENSORS`, `CONF_WATER_TEMP_TARGET`, `CONF_EXCLUDE_FROM_DEW_POINT`.
  - Mode keys: `WATER_TEMP_MODE_COOLING = "cooling"`, `WATER_TEMP_MODE_HEATING = "heating"`.
  - Defaults and tuning constants listed in Step 3.
  - `custom_components.adaptive_climate.validate_water_temp_control(config: dict) -> dict` — raises `vol.Invalid`.
  - `WATER_TEMP_CONTROL_SCHEMA`, `WATER_TEMP_COOLING_SCHEMA`, `WATER_TEMP_HEATING_SCHEMA`, `WATER_TEMP_EXTRA_SENSOR_SCHEMA` (all `None` in the no-HA stub branch).

- [ ] **Step 1: Write the failing test**

Create `tests/test_water_temp_config.py`:

```python
"""Tests for water_temp_control constants, schema and cross-key validation."""

from __future__ import annotations

import pytest
import voluptuous as vol

from custom_components.adaptive_climate import validate_water_temp_control
from custom_components.adaptive_climate.const import (
    CONF_EXCLUDE_FROM_DEW_POINT,
    CONF_SUPPLY_TEMPERATURE,
    CONF_WATER_TEMP_CONTROL,
    CONF_WATER_TEMP_COOLING,
    CONF_WATER_TEMP_DEW_POINT_MARGIN,
    CONF_WATER_TEMP_HEATING,
    CONF_WATER_TEMP_IDLE_DAYS,
    CONF_WATER_TEMP_MIN_SUPPLY_TEMP,
    CONF_WATER_TEMP_MIN_WRITE_INTERVAL,
    CONF_WATER_TEMP_RAMP_RATE,
    CONF_WATER_TEMP_RAMP_START,
    CONF_WATER_TEMP_TARGET,
    CONF_WATER_TEMP_TARGET_ENTITY,
    DEFAULT_WATER_TEMP_COOLING_RAMP_RATE,
    DEFAULT_WATER_TEMP_COOLING_RAMP_START,
    DEFAULT_WATER_TEMP_DEW_POINT_MARGIN,
    DEFAULT_WATER_TEMP_HEATING_RAMP_RATE,
    DEFAULT_WATER_TEMP_HEATING_RAMP_START,
    DEFAULT_WATER_TEMP_IDLE_DAYS,
    DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP,
    DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL,
    WATER_TEMP_MODE_COOLING,
    WATER_TEMP_MODE_HEATING,
)


def _cooling(entity: str = "number.hp_cool") -> dict:
    return {CONF_WATER_TEMP_TARGET_ENTITY: entity}


def _heating(entity: str = "number.hp_heat", target: float | None = 35.0) -> dict:
    block = {CONF_WATER_TEMP_TARGET_ENTITY: entity}
    if target is not None:
        block[CONF_WATER_TEMP_TARGET] = target
    return block


# --- constants -------------------------------------------------------------


def test_spec_defaults_are_the_user_approved_values():
    """Reviewer-kept defaults must not drift."""
    assert DEFAULT_WATER_TEMP_IDLE_DAYS == 7
    assert DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL == 1800
    assert DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP == 18.0
    assert DEFAULT_WATER_TEMP_DEW_POINT_MARGIN == 2.0
    assert DEFAULT_WATER_TEMP_COOLING_RAMP_START == 22.0
    assert DEFAULT_WATER_TEMP_COOLING_RAMP_RATE == 1.0
    assert DEFAULT_WATER_TEMP_HEATING_RAMP_START == 25.0
    assert DEFAULT_WATER_TEMP_HEATING_RAMP_RATE == 2.0


def test_config_key_names_match_the_yaml_surface():
    """Key strings are the public YAML surface — pin them."""
    assert CONF_WATER_TEMP_CONTROL == "water_temp_control"
    assert CONF_WATER_TEMP_COOLING == "cooling"
    assert CONF_WATER_TEMP_HEATING == "heating"
    assert CONF_WATER_TEMP_TARGET_ENTITY == "target_entity"
    assert CONF_WATER_TEMP_MIN_SUPPLY_TEMP == "min_supply_temp"
    assert CONF_WATER_TEMP_DEW_POINT_MARGIN == "dew_point_margin"
    assert CONF_WATER_TEMP_RAMP_START == "ramp_start"
    assert CONF_WATER_TEMP_RAMP_RATE == "ramp_rate"
    assert CONF_WATER_TEMP_IDLE_DAYS == "idle_days"
    assert CONF_WATER_TEMP_MIN_WRITE_INTERVAL == "min_write_interval"
    assert CONF_EXCLUDE_FROM_DEW_POINT == "exclude_from_dew_point"
    assert WATER_TEMP_MODE_COOLING == "cooling"
    assert WATER_TEMP_MODE_HEATING == "heating"


def test_margin_key_does_not_collide_with_cooling_supply_margin():
    """The new key must be distinct from the pre-existing, differently-scoped one."""
    from custom_components.adaptive_climate.const import CONF_COOLING_SUPPLY_MARGIN

    assert CONF_WATER_TEMP_DEW_POINT_MARGIN != CONF_COOLING_SUPPLY_MARGIN


# --- cross-key validator ---------------------------------------------------


def test_validator_passes_through_config_without_water_temp_block():
    config = {"sync_modes": True}
    assert validate_water_temp_control(config) is config


def test_validator_accepts_cooling_only():
    config = {CONF_WATER_TEMP_CONTROL: {CONF_WATER_TEMP_COOLING: _cooling()}}
    assert validate_water_temp_control(config) is config


def test_validator_accepts_heating_with_explicit_target():
    config = {CONF_WATER_TEMP_CONTROL: {CONF_WATER_TEMP_HEATING: _heating(target=35.0)}}
    assert validate_water_temp_control(config) is config


def test_validator_accepts_heating_target_falling_back_to_supply_temperature():
    config = {
        CONF_SUPPLY_TEMPERATURE: 40.0,
        CONF_WATER_TEMP_CONTROL: {CONF_WATER_TEMP_HEATING: _heating(target=None)},
    }
    assert validate_water_temp_control(config) is config


def test_validator_rejects_heating_with_no_target_anywhere():
    config = {CONF_WATER_TEMP_CONTROL: {CONF_WATER_TEMP_HEATING: _heating(target=None)}}
    with pytest.raises(vol.Invalid, match="supply_temperature"):
        validate_water_temp_control(config)


def test_validator_rejects_supply_temperature_fallback_outside_heating_range():
    """supply_temperature is validated to 25-80; the heating target range is 20-45."""
    config = {
        CONF_SUPPLY_TEMPERATURE: 70.0,
        CONF_WATER_TEMP_CONTROL: {CONF_WATER_TEMP_HEATING: _heating(target=None)},
    }
    with pytest.raises(vol.Invalid, match="outside the water_temp_control heating"):
        validate_water_temp_control(config)


def test_validator_rejects_identical_target_entities():
    config = {
        CONF_WATER_TEMP_CONTROL: {
            CONF_WATER_TEMP_COOLING: _cooling("number.hp_supply"),
            CONF_WATER_TEMP_HEATING: _heating("number.hp_supply", target=35.0),
        }
    }
    with pytest.raises(vol.Invalid, match="must differ"):
        validate_water_temp_control(config)


def test_validator_accepts_distinct_target_entities():
    config = {
        CONF_WATER_TEMP_CONTROL: {
            CONF_WATER_TEMP_COOLING: _cooling("number.hp_cool"),
            CONF_WATER_TEMP_HEATING: _heating("number.hp_heat", target=35.0),
        }
    }
    assert validate_water_temp_control(config) is config


# --- voluptuous schema -----------------------------------------------------


def test_schema_applies_all_defaults():
    from custom_components.adaptive_climate import WATER_TEMP_CONTROL_SCHEMA

    if WATER_TEMP_CONTROL_SCHEMA is None:
        pytest.skip("Home Assistant not installed; schema is stubbed to None")

    result = WATER_TEMP_CONTROL_SCHEMA(
        {
            CONF_WATER_TEMP_COOLING: {CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_cool"},
            CONF_WATER_TEMP_HEATING: {
                CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_heat",
                CONF_WATER_TEMP_TARGET: 35.0,
            },
        }
    )

    assert result[CONF_WATER_TEMP_IDLE_DAYS] == DEFAULT_WATER_TEMP_IDLE_DAYS
    assert result[CONF_WATER_TEMP_MIN_WRITE_INTERVAL] == DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL
    cooling = result[CONF_WATER_TEMP_COOLING]
    assert cooling[CONF_WATER_TEMP_MIN_SUPPLY_TEMP] == DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP
    assert cooling[CONF_WATER_TEMP_DEW_POINT_MARGIN] == DEFAULT_WATER_TEMP_DEW_POINT_MARGIN
    assert cooling[CONF_WATER_TEMP_RAMP_START] == DEFAULT_WATER_TEMP_COOLING_RAMP_START
    assert cooling[CONF_WATER_TEMP_RAMP_RATE] == DEFAULT_WATER_TEMP_COOLING_RAMP_RATE
    assert cooling["extra_sensors"] == []
    heating = result[CONF_WATER_TEMP_HEATING]
    assert heating[CONF_WATER_TEMP_RAMP_START] == DEFAULT_WATER_TEMP_HEATING_RAMP_START
    assert heating[CONF_WATER_TEMP_RAMP_RATE] == DEFAULT_WATER_TEMP_HEATING_RAMP_RATE


def test_schema_requires_cooling_target_entity():
    from custom_components.adaptive_climate import WATER_TEMP_CONTROL_SCHEMA

    if WATER_TEMP_CONTROL_SCHEMA is None:
        pytest.skip("Home Assistant not installed; schema is stubbed to None")

    with pytest.raises(vol.Invalid):
        WATER_TEMP_CONTROL_SCHEMA({CONF_WATER_TEMP_COOLING: {}})


def test_schema_rejects_heating_target_out_of_range():
    from custom_components.adaptive_climate import WATER_TEMP_CONTROL_SCHEMA

    if WATER_TEMP_CONTROL_SCHEMA is None:
        pytest.skip("Home Assistant not installed; schema is stubbed to None")

    with pytest.raises(vol.Invalid):
        WATER_TEMP_CONTROL_SCHEMA(
            {
                CONF_WATER_TEMP_HEATING: {
                    CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_heat",
                    CONF_WATER_TEMP_TARGET: 60.0,
                }
            }
        )


def test_schema_parses_extra_sensor_pairs():
    from custom_components.adaptive_climate import WATER_TEMP_CONTROL_SCHEMA

    if WATER_TEMP_CONTROL_SCHEMA is None:
        pytest.skip("Home Assistant not installed; schema is stubbed to None")

    result = WATER_TEMP_CONTROL_SCHEMA(
        {
            CONF_WATER_TEMP_COOLING: {
                CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_cool",
                "extra_sensors": [
                    {"humidity": "sensor.manifold_rh", "temperature": "sensor.manifold_temp"}
                ],
            }
        }
    )
    pair = result[CONF_WATER_TEMP_COOLING]["extra_sensors"][0]
    assert pair["humidity"] == "sensor.manifold_rh"
    assert pair["temperature"] == "sensor.manifold_temp"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_water_temp_config.py -v`
Expected: FAIL — `ImportError: cannot import name 'CONF_WATER_TEMP_CONTROL' from ...const`

- [ ] **Step 3: Add the constants**

Append to the end of `custom_components/adaptive_climate/const.py`:

```python
# ─────────────────────────────────────────────────────────────────────────────
# Water temperature control (dew-point cooling + startup ramps)
# ─────────────────────────────────────────────────────────────────────────────

# Domain-level config keys
CONF_WATER_TEMP_CONTROL = "water_temp_control"
CONF_WATER_TEMP_IDLE_DAYS = "idle_days"
CONF_WATER_TEMP_MIN_WRITE_INTERVAL = "min_write_interval"
CONF_WATER_TEMP_CONDENSATION_SENSOR = "condensation_sensor"
CONF_WATER_TEMP_COOLING = "cooling"
CONF_WATER_TEMP_HEATING = "heating"

# Per-mode config keys
CONF_WATER_TEMP_TARGET_ENTITY = "target_entity"
CONF_WATER_TEMP_MIN_SUPPLY_TEMP = "min_supply_temp"
CONF_WATER_TEMP_DEW_POINT_MARGIN = "dew_point_margin"
CONF_WATER_TEMP_FALLBACK_HUMIDITY = "fallback_humidity"
CONF_WATER_TEMP_RAMP_START = "ramp_start"
CONF_WATER_TEMP_RAMP_RATE = "ramp_rate"
CONF_WATER_TEMP_EXTRA_SENSORS = "extra_sensors"
CONF_WATER_TEMP_TARGET = "target"
CONF_WATER_TEMP_EXTRA_HUMIDITY = "humidity"
CONF_WATER_TEMP_EXTRA_TEMPERATURE = "temperature"

# Entity-level config key
CONF_EXCLUDE_FROM_DEW_POINT = "exclude_from_dew_point"

# Internal mode keys (also the persistence keys and diagnostic sensor values)
WATER_TEMP_MODE_COOLING = "cooling"
WATER_TEMP_MODE_HEATING = "heating"

# Defaults (spec-approved values — do not change without a spec amendment)
DEFAULT_WATER_TEMP_IDLE_DAYS = 7
DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL = 1800  # seconds
DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP = 18.0  # °C
DEFAULT_WATER_TEMP_DEW_POINT_MARGIN = 2.0  # °C above dew point
DEFAULT_WATER_TEMP_FALLBACK_HUMIDITY = 65.0  # % RH
DEFAULT_WATER_TEMP_COOLING_RAMP_START = 22.0  # °C
DEFAULT_WATER_TEMP_COOLING_RAMP_RATE = 1.0  # °C/day downward
DEFAULT_WATER_TEMP_HEATING_RAMP_START = 25.0  # °C
DEFAULT_WATER_TEMP_HEATING_RAMP_RATE = 2.0  # °C/day upward

# Heating target validation bounds (narrower than SUPPLY_TEMP_MIN/MAX, which
# also govern physics-based PID init).
WATER_TEMP_HEATING_TARGET_MIN = 20.0
WATER_TEMP_HEATING_TARGET_MAX = 45.0

# Write policy
DEFAULT_WATER_TEMP_STEP = 0.5  # fallback when the target entity exposes no step
WATER_TEMP_UPDATE_INTERVAL_SECONDS = 300  # recompute every 5 min
WATER_TEMP_STARTUP_DELAY_SECONDS = 30  # after HA start, let zones register + state restore

# Source scanning
WATER_TEMP_EMA_WINDOW_MINUTES = 20.0  # per-source RH smoothing time constant
WATER_TEMP_STALE_MINUTES = 60.0  # state.last_updated older than this = stale
WATER_TEMP_RH_MIN = 15.0  # % — below this RH reading is implausible
WATER_TEMP_RH_MAX = 100.0  # %
WATER_TEMP_AIR_TEMP_MIN = 5.0  # °C — below this air temp reading is implausible
WATER_TEMP_AIR_TEMP_MAX = 40.0  # °C
WATER_TEMP_BLIND_MIN_SUPPLY = 20.0  # °C floor when no source has a real reading
WATER_TEMP_WARN_INTERVAL_SECONDS = 3600  # rate limit for implausible/stale warnings

# Interlocks and learning gate
WATER_TEMP_INTERLOCK_STABILIZATION_SECONDS = 1800  # 30 min hold after interlock clears
WATER_TEMP_SETTLING_MINUTES = 60  # slowest heating type's settling window
WATER_TEMP_GATE_WRITE_DELTA = 1.0  # °C write change that (re)opens the learning gate

# Diagnostic sensor binding_constraint values
WATER_TEMP_BINDING_DEW_POINT = "dew_point"
WATER_TEMP_BINDING_MIN_SUPPLY = "min_supply"
WATER_TEMP_BINDING_RAMP = "ramp"
WATER_TEMP_BINDING_TARGET = "target"
WATER_TEMP_BINDING_INTERLOCK = "interlock"
WATER_TEMP_BINDING_BLIND = "blind"
```

- [ ] **Step 4: Add the validator and schemas to `__init__.py`**

In `custom_components/adaptive_climate/__init__.py`, add the new const imports to the existing `from .const import (...)` block:

```python
    CONF_WATER_TEMP_CONTROL,
    CONF_WATER_TEMP_COOLING,
    CONF_WATER_TEMP_HEATING,
    CONF_WATER_TEMP_TARGET,
    CONF_WATER_TEMP_TARGET_ENTITY,
    CONF_WATER_TEMP_MIN_SUPPLY_TEMP,
    CONF_WATER_TEMP_DEW_POINT_MARGIN,
    CONF_WATER_TEMP_FALLBACK_HUMIDITY,
    CONF_WATER_TEMP_RAMP_START,
    CONF_WATER_TEMP_RAMP_RATE,
    CONF_WATER_TEMP_EXTRA_SENSORS,
    CONF_WATER_TEMP_EXTRA_HUMIDITY,
    CONF_WATER_TEMP_EXTRA_TEMPERATURE,
    CONF_WATER_TEMP_IDLE_DAYS,
    CONF_WATER_TEMP_MIN_WRITE_INTERVAL,
    CONF_WATER_TEMP_CONDENSATION_SENSOR,
    DEFAULT_WATER_TEMP_IDLE_DAYS,
    DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL,
    DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP,
    DEFAULT_WATER_TEMP_DEW_POINT_MARGIN,
    DEFAULT_WATER_TEMP_FALLBACK_HUMIDITY,
    DEFAULT_WATER_TEMP_COOLING_RAMP_START,
    DEFAULT_WATER_TEMP_COOLING_RAMP_RATE,
    DEFAULT_WATER_TEMP_HEATING_RAMP_START,
    DEFAULT_WATER_TEMP_HEATING_RAMP_RATE,
    WATER_TEMP_HEATING_TARGET_MIN,
    WATER_TEMP_HEATING_TARGET_MAX,
```

Add the validator immediately **above** the `# Domain configuration schema` comment at line 171 (outside the `if HAS_HOMEASSISTANT:` block, so it is importable and testable without HA — voluptuous is always available):

```python
def validate_water_temp_control(config: dict[str, Any]) -> dict[str, Any]:
    """Validate ``water_temp_control`` against sibling domain keys.

    Runs as a domain-level ``vol.All`` wrapper because two rules reach outside
    ``WATER_TEMP_CONTROL_SCHEMA``:

    1. ``heating.target`` falls back to the domain-level ``supply_temperature``.
       Neither present is a configuration error.
    2. ``cooling.target_entity`` and ``heating.target_entity`` must differ —
       writing both halves to one entity would make the two controllers fight.

    Args:
        config: The validated ``adaptive_climate:`` domain config dict.

    Returns:
        The same dict, unchanged, when valid.

    Raises:
        vol.Invalid: When a rule above is violated.
    """
    water_temp = config.get(CONF_WATER_TEMP_CONTROL)
    if not water_temp:
        return config

    cooling = water_temp.get(CONF_WATER_TEMP_COOLING)
    heating = water_temp.get(CONF_WATER_TEMP_HEATING)

    if heating is not None and heating.get(CONF_WATER_TEMP_TARGET) is None:
        fallback = config.get(CONF_SUPPLY_TEMPERATURE)
        if fallback is None:
            raise vol.Invalid(
                "water_temp_control.heating.target is required when the domain-level "
                "supply_temperature is not configured"
            )
        if not WATER_TEMP_HEATING_TARGET_MIN <= float(fallback) <= WATER_TEMP_HEATING_TARGET_MAX:
            raise vol.Invalid(
                f"supply_temperature ({fallback}°C) is outside the water_temp_control heating "
                f"target range ({WATER_TEMP_HEATING_TARGET_MIN}-{WATER_TEMP_HEATING_TARGET_MAX}°C); "
                "set water_temp_control.heating.target explicitly"
            )

    if cooling is not None and heating is not None:
        cool_entity = cooling.get(CONF_WATER_TEMP_TARGET_ENTITY)
        heat_entity = heating.get(CONF_WATER_TEMP_TARGET_ENTITY)
        if cool_entity == heat_entity:
            raise vol.Invalid(
                "water_temp_control.cooling.target_entity and "
                "water_temp_control.heating.target_entity must differ "
                f"(both set to '{cool_entity}')"
            )

    return config
```

Inside the `if HAS_HOMEASSISTANT:` block, add these schemas after `AUTO_MODE_SWITCHING_SCHEMA` (which ends at line 223) and before `CONFIG_SCHEMA`:

```python
    # Water temperature control — extra (non-zone) humidity/temperature pair
    WATER_TEMP_EXTRA_SENSOR_SCHEMA = vol.Schema(
        {
            vol.Required(CONF_WATER_TEMP_EXTRA_HUMIDITY): cv.entity_id,
            vol.Required(CONF_WATER_TEMP_EXTRA_TEMPERATURE): cv.entity_id,
        }
    )

    # Water temperature control — cooling half (dew-point driven)
    WATER_TEMP_COOLING_SCHEMA = vol.Schema(
        {
            vol.Required(CONF_WATER_TEMP_TARGET_ENTITY): cv.entity_id,
            vol.Optional(CONF_WATER_TEMP_MIN_SUPPLY_TEMP, default=DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP): vol.All(
                vol.Coerce(float),
                vol.Range(min=5.0, max=30.0, msg="min_supply_temp must be between 5 and 30°C"),
            ),
            vol.Optional(CONF_WATER_TEMP_DEW_POINT_MARGIN, default=DEFAULT_WATER_TEMP_DEW_POINT_MARGIN): vol.All(
                vol.Coerce(float),
                vol.Range(min=0.0, max=10.0, msg="dew_point_margin must be between 0 and 10°C"),
            ),
            vol.Optional(CONF_WATER_TEMP_FALLBACK_HUMIDITY, default=DEFAULT_WATER_TEMP_FALLBACK_HUMIDITY): vol.All(
                vol.Coerce(float),
                vol.Range(min=15.0, max=100.0, msg="fallback_humidity must be between 15 and 100%"),
            ),
            vol.Optional(CONF_WATER_TEMP_RAMP_START, default=DEFAULT_WATER_TEMP_COOLING_RAMP_START): vol.All(
                vol.Coerce(float),
                vol.Range(min=5.0, max=40.0, msg="cooling ramp_start must be between 5 and 40°C"),
            ),
            vol.Optional(CONF_WATER_TEMP_RAMP_RATE, default=DEFAULT_WATER_TEMP_COOLING_RAMP_RATE): vol.All(
                vol.Coerce(float),
                vol.Range(min=0.1, max=10.0, msg="cooling ramp_rate must be between 0.1 and 10°C/day"),
            ),
            vol.Optional(CONF_WATER_TEMP_EXTRA_SENSORS, default=[]): vol.All(
                cv.ensure_list, [WATER_TEMP_EXTRA_SENSOR_SCHEMA]
            ),
        }
    )

    # Water temperature control — heating half (fixed target + ramp)
    WATER_TEMP_HEATING_SCHEMA = vol.Schema(
        {
            vol.Required(CONF_WATER_TEMP_TARGET_ENTITY): cv.entity_id,
            # No default: absence triggers the supply_temperature fallback in
            # validate_water_temp_control().
            vol.Optional(CONF_WATER_TEMP_TARGET): vol.All(
                vol.Coerce(float),
                vol.Range(
                    min=WATER_TEMP_HEATING_TARGET_MIN,
                    max=WATER_TEMP_HEATING_TARGET_MAX,
                    msg=(
                        f"heating target must be between {WATER_TEMP_HEATING_TARGET_MIN} "
                        f"and {WATER_TEMP_HEATING_TARGET_MAX}°C"
                    ),
                ),
            ),
            vol.Optional(CONF_WATER_TEMP_RAMP_START, default=DEFAULT_WATER_TEMP_HEATING_RAMP_START): vol.All(
                vol.Coerce(float),
                vol.Range(min=15.0, max=60.0, msg="heating ramp_start must be between 15 and 60°C"),
            ),
            vol.Optional(CONF_WATER_TEMP_RAMP_RATE, default=DEFAULT_WATER_TEMP_HEATING_RAMP_RATE): vol.All(
                vol.Coerce(float),
                vol.Range(min=0.1, max=10.0, msg="heating ramp_rate must be between 0.1 and 10°C/day"),
            ),
        }
    )

    # Water temperature control — top level
    WATER_TEMP_CONTROL_SCHEMA = vol.Schema(
        {
            vol.Optional(CONF_WATER_TEMP_IDLE_DAYS, default=DEFAULT_WATER_TEMP_IDLE_DAYS): vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=365, msg="idle_days must be between 1 and 365"),
            ),
            vol.Optional(
                CONF_WATER_TEMP_MIN_WRITE_INTERVAL, default=DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=0, max=86400, msg="min_write_interval must be between 0 and 86400 seconds"),
            ),
            vol.Optional(CONF_WATER_TEMP_CONDENSATION_SENSOR): cv.entity_id,
            vol.Optional(CONF_WATER_TEMP_COOLING): WATER_TEMP_COOLING_SCHEMA,
            vol.Optional(CONF_WATER_TEMP_HEATING): WATER_TEMP_HEATING_SCHEMA,
        }
    )
```

Add the key to the DOMAIN dict, right after the `CONF_COOLING_SUPPLY_MARGIN` entry at line 307:

```python
                    # Water temperature control (dew-point cooling + startup ramps)
                    vol.Optional(CONF_WATER_TEMP_CONTROL): WATER_TEMP_CONTROL_SCHEMA,
```

Wrap the DOMAIN schema in the cross-key validator — replace `DOMAIN: vol.Schema(` at line 227 with `DOMAIN: vol.All(vol.Schema(` and close it after the schema's `}` and `)` at lines 308-309 so it reads:

```python
                }
            ),
            validate_water_temp_control,
        )
        },
        extra=vol.ALLOW_EXTRA,  # Allow other domains in config
    )
```

Extend the no-HA stub branch at lines 313-317:

```python
else:
    # Provide stub for testing without Home Assistant
    CONFIG_SCHEMA = None
    THERMAL_GROUP_SCHEMA = None
    MANIFOLD_SCHEMA = None
    WATER_TEMP_EXTRA_SENSOR_SCHEMA = None
    WATER_TEMP_COOLING_SCHEMA = None
    WATER_TEMP_HEATING_SCHEMA = None
    WATER_TEMP_CONTROL_SCHEMA = None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_water_temp_config.py tests/test_init.py tests/test_const.py -v`
Expected: PASS — new file all green, no regressions in `test_init.py` / `test_const.py`

- [ ] **Step 6: Lint and typecheck**

Run: `ruff check custom_components/adaptive_climate/const.py custom_components/adaptive_climate/__init__.py tests/test_water_temp_config.py && pyright custom_components/adaptive_climate/const.py custom_components/adaptive_climate/__init__.py`
Expected: no findings

- [ ] **Step 7: Commit**

```bash
git add custom_components/adaptive_climate/const.py custom_components/adaptive_climate/__init__.py tests/test_water_temp_config.py
git commit -m "feat(config): add water_temp_control schema and cross-key validation"
```

---

### Task 3: Zone registration data for dew point scanning

**Files:**
- Modify: `custom_components/adaptive_climate/climate_setup.py:89` (platform schema), `climate_setup.py:408-417` (zone_data)
- Test: `tests/test_climate_setup.py` (append)

**Interfaces:**
- Consumes: `const.CONF_EXCLUDE_FROM_DEW_POINT`, `const.CONF_HUMIDITY_SENSOR` (Task 2).
- Produces: `coordinator.register_zone` zone_data now carries `"humidity_sensor": str | None` and `"exclude_from_dew_point": bool`. The scanner in Task 5 reads exactly these two keys.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_climate_setup.py`:

```python
class TestDewPointZoneData:
    """Zone registration must expose what the dew point scanner needs."""

    def test_platform_schema_accepts_exclude_from_dew_point(self):
        """The entity-level opt-out is a valid platform key."""
        from custom_components.adaptive_climate import const
        from custom_components.adaptive_climate.climate_setup import PLATFORM_SCHEMA

        result = PLATFORM_SCHEMA(
            {
                "platform": "adaptive_climate",
                "name": "Bathroom",
                const.CONF_SENSOR: "sensor.bathroom_temp",
                const.CONF_HEATER: ["switch.bathroom_valve"],
                const.CONF_EXCLUDE_FROM_DEW_POINT: True,
            }
        )
        assert result[const.CONF_EXCLUDE_FROM_DEW_POINT] is True

    def test_platform_schema_defaults_exclude_from_dew_point_to_false(self):
        """Zones opt in to the scan by default."""
        from custom_components.adaptive_climate import const
        from custom_components.adaptive_climate.climate_setup import PLATFORM_SCHEMA

        result = PLATFORM_SCHEMA(
            {
                "platform": "adaptive_climate",
                "name": "Living Room",
                const.CONF_SENSOR: "sensor.living_temp",
                const.CONF_HEATER: ["switch.living_valve"],
            }
        )
        assert result[const.CONF_EXCLUDE_FROM_DEW_POINT] is False

    def test_zone_data_carries_humidity_sensor_and_exclusion_flag(self):
        """register_zone's payload must include both dew-point keys."""
        from custom_components.adaptive_climate import const
        from custom_components.adaptive_climate.climate_setup import build_dew_point_zone_data

        config = {
            const.CONF_HUMIDITY_SENSOR: "sensor.bathroom_rh",
            const.CONF_EXCLUDE_FROM_DEW_POINT: True,
        }
        assert build_dew_point_zone_data(config) == {
            "humidity_sensor": "sensor.bathroom_rh",
            "exclude_from_dew_point": True,
        }

    def test_zone_data_defaults_when_nothing_configured(self):
        """A zone with no humidity sensor still registers both keys."""
        from custom_components.adaptive_climate.climate_setup import build_dew_point_zone_data

        assert build_dew_point_zone_data({}) == {
            "humidity_sensor": None,
            "exclude_from_dew_point": False,
        }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_climate_setup.py::TestDewPointZoneData -v`
Expected: FAIL — `ImportError: cannot import name 'build_dew_point_zone_data'` and schema `vol.Invalid` on the unknown key

- [ ] **Step 3: Write minimal implementation**

In `custom_components/adaptive_climate/climate_setup.py`, add to `PLATFORM_SCHEMA` directly after the `CONF_HUMIDITY_SENSOR` line (line 89):

```python
        vol.Optional(const.CONF_EXCLUDE_FROM_DEW_POINT, default=False): cv.boolean,
```

Add this helper just above `async_setup_platform` (i.e. after `_resolve_pwm`, around line 216):

```python
def build_dew_point_zone_data(config: ConfigType) -> dict[str, Any]:
    """Return the zone_data keys the water-temperature dew point scanner reads.

    Extracted as a helper so the contract between ``register_zone`` and
    ``DewPointScanner`` is directly unit-testable.

    Args:
        config: The validated entity platform config.

    Returns:
        Dict with ``humidity_sensor`` (entity id or None) and
        ``exclude_from_dew_point`` (bool).
    """
    return {
        "humidity_sensor": config.get(const.CONF_HUMIDITY_SENSOR),
        "exclude_from_dew_point": bool(config.get(const.CONF_EXCLUDE_FROM_DEW_POINT, False)),
    }
```

Add `Any` to the `typing` import at the top of the file if it is not already imported.

Then in the `zone_data` literal at lines 408-417, add the two keys after `"window_orientation"`:

```python
            "window_orientation": config.get(const.CONF_WINDOW_ORIENTATION),
            **build_dew_point_zone_data(config),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_climate_setup.py -v`
Expected: PASS — new class green, existing tests unaffected

- [ ] **Step 5: Lint and typecheck**

Run: `ruff check custom_components/adaptive_climate/climate_setup.py tests/test_climate_setup.py && pyright custom_components/adaptive_climate/climate_setup.py`
Expected: no findings

- [ ] **Step 6: Commit**

```bash
git add custom_components/adaptive_climate/climate_setup.py tests/test_climate_setup.py
git commit -m "feat(zones): expose humidity sensor and dew point exclusion in zone data"
```

---

### Task 4: Coordinator zone-mode and zone-temperature helpers

**Files:**
- Modify: `custom_components/adaptive_climate/coordinator.py:565` (insert after `get_active_zones`)
- Test: `tests/test_coordinator.py` (append)

**Interfaces:**
- Consumes: `self._zones` (zone_data with `climate_entity_id`), `self.hass.states`.
- Produces:
  - `coordinator.get_zones_in_mode(hvac_mode: str) -> dict[str, dict[str, Any]]` — zones whose **climate entity state** equals `hvac_mode`. Deliberately not `get_active_zones()`, which filters on live demand and drops satisfied zones, and is empty right after a restart.
  - `coordinator.get_zone_current_temp(zone_id: str) -> float | None` — the zone's climate entity `current_temperature` attribute. `coordinator.update_zone_temp` has no production callers, so `get_zone_temps()` is always `{}` in production.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_coordinator.py`:

```python
class TestZoneModeHelpers:
    """get_zones_in_mode / get_zone_current_temp read hass.states, not demand state."""

    @staticmethod
    def _coordinator_with_zones(zones):
        from unittest.mock import MagicMock

        from custom_components.adaptive_climate.coordinator import (
            AdaptiveThermostatCoordinator,
        )

        coordinator = AdaptiveThermostatCoordinator.__new__(AdaptiveThermostatCoordinator)
        coordinator._zones = zones
        coordinator._demand_states = {}
        coordinator.hass = MagicMock()
        return coordinator

    @staticmethod
    def _state(state_value, attributes=None):
        from unittest.mock import MagicMock

        state = MagicMock()
        state.state = state_value
        state.attributes = attributes or {}
        return state

    def test_returns_only_zones_whose_entity_state_matches(self):
        coordinator = self._coordinator_with_zones(
            {
                "living": {"climate_entity_id": "climate.living"},
                "bedroom": {"climate_entity_id": "climate.bedroom"},
                "attic": {"climate_entity_id": "climate.attic"},
            }
        )
        states = {
            "climate.living": self._state("cool"),
            "climate.bedroom": self._state("cool"),
            "climate.attic": self._state("off"),
        }
        coordinator.hass.states.get = states.get

        result = coordinator.get_zones_in_mode("cool")
        assert set(result) == {"living", "bedroom"}

    def test_includes_satisfied_zones_that_have_no_demand(self):
        """Demand is irrelevant — a satisfied COOL zone still counts."""
        coordinator = self._coordinator_with_zones({"living": {"climate_entity_id": "climate.living"}})
        coordinator._demand_states = {"living": {"demand": False, "mode": "cool"}}
        coordinator.hass.states.get = {"climate.living": self._state("cool")}.get

        assert "living" in coordinator.get_zones_in_mode("cool")

    def test_skips_zones_with_missing_state_or_entity_id(self):
        coordinator = self._coordinator_with_zones(
            {
                "ghost": {"climate_entity_id": "climate.ghost"},
                "nameless": {},
            }
        )
        coordinator.hass.states.get = lambda _entity_id: None

        assert coordinator.get_zones_in_mode("cool") == {}

    def test_get_zone_current_temp_reads_entity_attribute(self):
        coordinator = self._coordinator_with_zones({"living": {"climate_entity_id": "climate.living"}})
        coordinator.hass.states.get = {
            "climate.living": self._state("cool", {"current_temperature": 23.4})
        }.get

        assert coordinator.get_zone_current_temp("living") == 23.4

    def test_get_zone_current_temp_returns_none_for_missing_data(self):
        coordinator = self._coordinator_with_zones({"living": {"climate_entity_id": "climate.living"}})
        coordinator.hass.states.get = {"climate.living": self._state("cool", {})}.get

        assert coordinator.get_zone_current_temp("living") is None
        assert coordinator.get_zone_current_temp("nope") is None

    def test_get_zone_current_temp_rejects_non_numeric_attribute(self):
        coordinator = self._coordinator_with_zones({"living": {"climate_entity_id": "climate.living"}})
        coordinator.hass.states.get = {
            "climate.living": self._state("cool", {"current_temperature": "unknown"})
        }.get

        assert coordinator.get_zone_current_temp("living") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_coordinator.py::TestZoneModeHelpers -v`
Expected: FAIL — `AttributeError: 'AdaptiveThermostatCoordinator' object has no attribute 'get_zones_in_mode'`

- [ ] **Step 3: Write minimal implementation**

In `custom_components/adaptive_climate/coordinator.py`, insert directly after `get_active_zones` (which ends at line 565):

```python
    def get_zones_in_mode(self, hvac_mode: str) -> dict[str, dict[str, Any]]:
        """Get zones whose climate entity is currently in the given HVAC mode.

        Unlike :meth:`get_active_zones` this does **not** filter on live demand,
        so a COOL zone that is momentarily satisfied is still returned.  Reading
        the entity state (rather than ``_demand_states``) is also valid
        immediately after a restart, before any demand update has arrived.

        Args:
            hvac_mode: HVAC mode string to match ("heat", "cool", "off").

        Returns:
            Dictionary of zone_id -> zone_data for matching zones.
        """
        zones_in_mode: dict[str, dict[str, Any]] = {}
        for zone_id, zone_data in self._zones.items():
            climate_entity_id = zone_data.get("climate_entity_id")
            if not climate_entity_id:
                continue
            state = self.hass.states.get(climate_entity_id)
            if state is None or state.state != hvac_mode:
                continue
            zones_in_mode[zone_id] = zone_data
        return zones_in_mode

    def get_zone_current_temp(self, zone_id: str) -> float | None:
        """Get a zone's current temperature from its climate entity attribute.

        ``update_zone_temp`` has no production callers, so the registry's
        ``current_temp`` map is empty outside tests.  The entity's
        ``current_temperature`` attribute is the authoritative source.

        Args:
            zone_id: Unique identifier for the zone.

        Returns:
            Current temperature in °C, or None when unavailable/non-numeric.
        """
        zone_data = self._zones.get(zone_id)
        if zone_data is None:
            return None
        climate_entity_id = zone_data.get("climate_entity_id")
        if not climate_entity_id:
            return None
        state = self.hass.states.get(climate_entity_id)
        if state is None:
            return None
        temp = state.attributes.get("current_temperature")
        if isinstance(temp, bool) or not isinstance(temp, (int, float)):
            return None
        return float(temp)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_coordinator.py -v`
Expected: PASS — new class green, existing coordinator tests unaffected

- [ ] **Step 5: Lint and typecheck**

Run: `ruff check custom_components/adaptive_climate/coordinator.py tests/test_coordinator.py && pyright custom_components/adaptive_climate/coordinator.py`
Expected: no findings

- [ ] **Step 6: Commit**

```bash
git add custom_components/adaptive_climate/coordinator.py tests/test_coordinator.py
git commit -m "feat(coordinator): add entity-state zone mode and temperature helpers"
```

---

### Task 5: Dew point source scanner

**Files:**
- Create: `custom_components/adaptive_climate/managers/water_temp_sources.py`
- Test: `tests/test_water_temp_sources.py`

**Interfaces:**
- Consumes: `dew_point()` (Task 1), water-temp constants (Task 2), zone_data `humidity_sensor` / `exclude_from_dew_point` (Task 3), `coordinator.get_zones_in_mode` / `get_zone_current_temp` (Task 4).
- Produces:
  - `SourceReading` frozen dataclass: `key: str`, `rh_pct: float`, `temp_c: float`, `dew_point_c: float`, `real: bool`, `temp_source: str` (`"device"` | `"climate"` | `"entity"`).
  - `DewPointScan` frozen dataclass: `dew_point: float | None`, `worst_source: str | None`, `blind: bool`, `readings: tuple[SourceReading, ...]`.
  - `DewPointScanner(hass, coordinator, extra_sensors, fallback_humidity)` with `scan(now: datetime) -> DewPointScan`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_water_temp_sources.py`:

```python
"""Tests for the water-temperature dew point source scanner."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from custom_components.adaptive_climate.managers.water_temp_sources import (
    DewPointScanner,
)

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def make_state(value, attributes=None, last_updated=NOW):
    state = MagicMock()
    state.state = value
    state.attributes = attributes or {}
    state.last_updated = last_updated
    return state


class FakeWorld:
    """Minimal hass/coordinator double driven by a plain dict of states."""

    def __init__(self):
        self.states_map: dict[str, MagicMock] = {}
        self.zones: dict[str, dict] = {}
        self.hass = MagicMock()
        self.hass.states.get = self.states_map.get
        self.coordinator = MagicMock()
        self.coordinator.get_zones_in_mode = lambda mode: self.zones
        self.coordinator.get_zone_current_temp = self._zone_temp

    def _zone_temp(self, zone_id):
        zone = self.zones.get(zone_id, {})
        state = self.states_map.get(zone.get("climate_entity_id", ""))
        if state is None:
            return None
        temp = state.attributes.get("current_temperature")
        return float(temp) if isinstance(temp, (int, float)) else None

    def add_zone(self, zone_id, *, humidity, rh, room_temp, exclude=False, overrides=None, rh_updated=NOW):
        entity = f"climate.{zone_id}"
        self.zones[zone_id] = {
            "climate_entity_id": entity,
            "humidity_sensor": humidity,
            "exclude_from_dew_point": exclude,
        }
        self.states_map[entity] = make_state(
            "cool",
            {
                "current_temperature": room_temp,
                "status": {"overrides": overrides or []},
            },
        )
        if humidity is not None:
            self.states_map[humidity] = make_state(str(rh), last_updated=rh_updated)

    def scanner(self, extra_sensors=None, fallback_humidity=65.0):
        return DewPointScanner(
            self.hass,
            self.coordinator,
            extra_sensors=extra_sensors or [],
            fallback_humidity=fallback_humidity,
        )


# --- worst-source selection ------------------------------------------------


def test_worst_source_is_the_highest_dew_point():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=50.0, room_temp=24.0)
    world.add_zone("kitchen", humidity="sensor.kitchen_rh", rh=70.0, room_temp=24.0)

    scan = world.scanner().scan(NOW)

    assert scan.blind is False
    assert scan.worst_source == "kitchen"
    assert scan.dew_point == pytest.approx(18.36, abs=0.1)


def test_extra_sensors_are_scanned_regardless_of_mode():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=45.0, room_temp=24.0)
    world.states_map["sensor.manifold_rh"] = make_state("85")
    world.states_map["sensor.manifold_temp"] = make_state("18")

    scan = world.scanner(
        extra_sensors=[{"humidity": "sensor.manifold_rh", "temperature": "sensor.manifold_temp"}]
    ).scan(NOW)

    assert scan.worst_source == "extra:sensor.manifold_rh"
    assert scan.dew_point == pytest.approx(15.5, abs=0.2)


def test_zones_without_a_humidity_sensor_are_skipped():
    world = FakeWorld()
    world.add_zone("living", humidity=None, rh=None, room_temp=24.0)
    world.add_zone("kitchen", humidity="sensor.kitchen_rh", rh=55.0, room_temp=24.0)

    scan = world.scanner().scan(NOW)

    assert [r.key for r in scan.readings] == ["kitchen"]


# --- exclusions ------------------------------------------------------------


def test_excluded_zone_is_omitted():
    world = FakeWorld()
    world.add_zone("bathroom", humidity="sensor.bath_rh", rh=90.0, room_temp=24.0, exclude=True)
    world.add_zone("living", humidity="sensor.living_rh", rh=50.0, room_temp=24.0)

    scan = world.scanner().scan(NOW)

    assert [r.key for r in scan.readings] == ["living"]


@pytest.mark.parametrize("humidity_state", ["paused", "stabilizing"])
def test_humidity_paused_zone_is_omitted(humidity_state):
    """A shower in progress is local and transient — the detector already knows."""
    world = FakeWorld()
    world.add_zone(
        "bathroom",
        humidity="sensor.bath_rh",
        rh=95.0,
        room_temp=24.0,
        overrides=[{"type": "humidity", "state": humidity_state}],
    )
    world.add_zone("living", humidity="sensor.living_rh", rh=50.0, room_temp=24.0)

    scan = world.scanner().scan(NOW)

    assert [r.key for r in scan.readings] == ["living"]


# --- temperature pairing ---------------------------------------------------


def test_temp_pairing_prefers_a_sensor_on_the_same_device():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=60.0, room_temp=19.0)
    world.states_map["sensor.living_device_temp"] = make_state("26.0")

    scanner = world.scanner()
    scanner._find_paired_temp_entity = lambda _entity_id: "sensor.living_device_temp"
    scan = scanner.scan(NOW)

    reading = scan.readings[0]
    assert reading.temp_source == "device"
    assert reading.temp_c == pytest.approx(26.0)


def test_temp_pairing_falls_back_to_zone_current_temperature():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=60.0, room_temp=25.0)

    scanner = world.scanner()
    scanner._find_paired_temp_entity = lambda _entity_id: None
    scan = scanner.scan(NOW)

    reading = scan.readings[0]
    assert reading.temp_source == "climate"
    assert reading.temp_c == pytest.approx(25.0)


def test_extra_sensor_pair_uses_the_configured_temperature_entity():
    world = FakeWorld()
    world.states_map["sensor.manifold_rh"] = make_state("70")
    world.states_map["sensor.manifold_temp"] = make_state("17.5")

    scan = world.scanner(
        extra_sensors=[{"humidity": "sensor.manifold_rh", "temperature": "sensor.manifold_temp"}]
    ).scan(NOW)

    assert scan.readings[0].temp_source == "entity"
    assert scan.readings[0].temp_c == pytest.approx(17.5)


# --- plausibility ----------------------------------------------------------


@pytest.mark.parametrize("rh", [0.0, 1.0, 101.0])
def test_implausible_rh_uses_fallback_humidity(rh):
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=rh, room_temp=24.0)

    scan = world.scanner(fallback_humidity=65.0).scan(NOW)

    reading = scan.readings[0]
    assert reading.rh_pct == pytest.approx(65.0)
    assert reading.real is False


@pytest.mark.parametrize("room_temp", [3.0, 45.0])
def test_implausible_temperature_drops_the_source(room_temp):
    """No usable temperature means no computable dew point for that source."""
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=55.0, room_temp=room_temp)

    scan = world.scanner().scan(NOW)

    assert scan.readings == ()
    assert scan.blind is True


# --- staleness -------------------------------------------------------------


def test_stale_reading_uses_max_of_last_ema_and_fallback():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=80.0, room_temp=24.0)
    scanner = world.scanner(fallback_humidity=65.0)

    scanner.scan(NOW)  # seeds the EMA at 80%

    world.states_map["sensor.living_rh"] = make_state("80", last_updated=NOW - timedelta(minutes=120))
    scan = scanner.scan(NOW + timedelta(minutes=5))

    reading = scan.readings[0]
    assert reading.rh_pct == pytest.approx(80.0)  # last EMA beats the 65% fallback
    assert reading.real is False


def test_stale_reading_with_no_history_uses_fallback():
    world = FakeWorld()
    world.add_zone(
        "living",
        humidity="sensor.living_rh",
        rh=40.0,
        room_temp=24.0,
        rh_updated=NOW - timedelta(minutes=90),
    )

    scan = world.scanner(fallback_humidity=65.0).scan(NOW)

    assert scan.readings[0].rh_pct == pytest.approx(65.0)
    assert scan.readings[0].real is False


# --- EMA smoothing ---------------------------------------------------------


def test_ema_damps_a_single_humidity_spike():
    """One shower must not lock out house-wide cooling."""
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=50.0, room_temp=24.0)
    scanner = world.scanner()

    first = scanner.scan(NOW)
    assert first.readings[0].rh_pct == pytest.approx(50.0)  # first sample seeds

    world.states_map["sensor.living_rh"] = make_state("90")
    second = scanner.scan(NOW + timedelta(minutes=5))

    assert 50.0 < second.readings[0].rh_pct < 70.0


def test_ema_converges_toward_a_sustained_level():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=50.0, room_temp=24.0)
    scanner = world.scanner()
    scanner.scan(NOW)

    world.states_map["sensor.living_rh"] = make_state("70")
    last = 50.0
    for minutes in range(5, 125, 5):
        scan = scanner.scan(NOW + timedelta(minutes=minutes))
        assert scan.readings[0].rh_pct >= last
        last = scan.readings[0].rh_pct

    assert last == pytest.approx(70.0, abs=0.5)


# --- blind mode ------------------------------------------------------------


def test_blind_when_every_source_is_fallback_only():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=0.0, room_temp=24.0)

    scan = world.scanner().scan(NOW)

    assert scan.blind is True
    assert scan.dew_point is not None  # still computed from the fallback


def test_blind_when_no_sources_at_all():
    world = FakeWorld()

    scan = world.scanner().scan(NOW)

    assert scan.blind is True
    assert scan.dew_point is None
    assert scan.worst_source is None


def test_not_blind_when_at_least_one_real_reading_exists():
    world = FakeWorld()
    world.add_zone("living", humidity="sensor.living_rh", rh=0.0, room_temp=24.0)
    world.add_zone("kitchen", humidity="sensor.kitchen_rh", rh=55.0, room_temp=24.0)

    scan = world.scanner().scan(NOW)

    assert scan.blind is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_water_temp_sources.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '...managers.water_temp_sources'`

- [ ] **Step 3: Write minimal implementation**

Create `custom_components/adaptive_climate/managers/water_temp_sources.py`:

```python
"""Dew point source scanning for water temperature control.

Enumerates every humidity source that constrains how cold the cooling supply
water may run, pairs each with a co-located temperature, smooths the humidity,
applies plausibility/staleness guards, and returns the worst (highest) dew
point.  Reads only ``hass.states`` and the coordinator's zone registry — it
never reaches into thermostat entity internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
import math
from typing import TYPE_CHECKING, Any

from ..const import (
    WATER_TEMP_AIR_TEMP_MAX,
    WATER_TEMP_AIR_TEMP_MIN,
    WATER_TEMP_EMA_WINDOW_MINUTES,
    WATER_TEMP_RH_MAX,
    WATER_TEMP_RH_MIN,
    WATER_TEMP_STALE_MINUTES,
    WATER_TEMP_WARN_INTERVAL_SECONDS,
)
from ..helpers.dew_point import dew_point

try:
    from homeassistant.components.climate import HVACMode
    from homeassistant.helpers import entity_registry as er
except ImportError:  # pragma: no cover - test environment without full HA
    HVACMode = None  # type: ignore[assignment] - HA boundary stub for no-HA test runs
    er = None  # type: ignore[assignment] - HA boundary stub for no-HA test runs

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..coordinator import AdaptiveThermostatCoordinator

_LOGGER = logging.getLogger(__name__)

_COOL_MODE = "cool"

TEMP_SOURCE_DEVICE = "device"
TEMP_SOURCE_CLIMATE = "climate"
TEMP_SOURCE_ENTITY = "entity"


@dataclass(frozen=True)
class SourceReading:
    """One resolved humidity source and its computed dew point."""

    key: str
    rh_pct: float
    temp_c: float
    dew_point_c: float
    real: bool
    temp_source: str


@dataclass(frozen=True)
class DewPointScan:
    """Result of one full scan across all sources."""

    dew_point: float | None
    worst_source: str | None
    blind: bool
    readings: tuple[SourceReading, ...]


class DewPointScanner:
    """Scan zones and extra sensor pairs for the worst-case indoor dew point."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: AdaptiveThermostatCoordinator,
        extra_sensors: list[dict[str, str]],
        fallback_humidity: float,
        ema_window_minutes: float = WATER_TEMP_EMA_WINDOW_MINUTES,
        stale_after_minutes: float = WATER_TEMP_STALE_MINUTES,
    ) -> None:
        """Initialize the scanner.

        Args:
            hass: Home Assistant instance.
            coordinator: Zone registry, used for COOL-mode zones and zone temps.
            extra_sensors: List of ``{"humidity": ..., "temperature": ...}`` pairs.
            fallback_humidity: RH in % used when a source has no usable reading.
            ema_window_minutes: Time constant of the per-source RH EMA.
            stale_after_minutes: ``state.last_updated`` age past which RH is stale.
        """
        self._hass = hass
        self._coordinator = coordinator
        self._extra_sensors = extra_sensors
        self._fallback_humidity = fallback_humidity
        self._ema_window_minutes = ema_window_minutes
        self._stale_after_minutes = stale_after_minutes

        self._ema: dict[str, float] = {}
        self._ema_updated: dict[str, datetime] = {}
        self._temp_source_logged: set[str] = set()
        self._last_warned: dict[str, datetime] = {}

    # ── public API ───────────────────────────────────────────────────────────

    def scan(self, now: datetime) -> DewPointScan:
        """Scan every source and return the worst-case dew point.

        Args:
            now: Current wall-clock time (``dt_util.utcnow()`` from the caller).

        Returns:
            A :class:`DewPointScan`.  ``blind`` is True when no source produced
            a plausible, fresh reading — the caller must then floor the supply
            temperature conservatively.
        """
        readings: list[SourceReading] = []
        readings.extend(self._scan_zones(now))
        readings.extend(self._scan_extra_sensors(now))

        if not readings:
            self._warn_once("no_sources", "Water temp control: no dew point sources available")
            return DewPointScan(dew_point=None, worst_source=None, blind=True, readings=())

        worst = max(readings, key=lambda reading: reading.dew_point_c)
        blind = not any(reading.real for reading in readings)
        if blind:
            self._warn_once(
                "blind",
                "Water temp control: no plausible, fresh humidity reading from any source — "
                "running blind on fallback humidity",
            )

        return DewPointScan(
            dew_point=worst.dew_point_c,
            worst_source=worst.key,
            blind=blind,
            readings=tuple(readings),
        )

    # ── source enumeration ───────────────────────────────────────────────────

    def _scan_zones(self, now: datetime) -> list[SourceReading]:
        """Build readings for every eligible COOL-mode zone."""
        readings: list[SourceReading] = []
        cool_mode = HVACMode.COOL if HVACMode is not None else _COOL_MODE

        for zone_id, zone_data in self._coordinator.get_zones_in_mode(cool_mode).items():
            humidity_entity_id = zone_data.get("humidity_sensor")
            if not humidity_entity_id:
                continue
            if zone_data.get("exclude_from_dew_point"):
                continue
            if self._zone_humidity_paused(zone_data):
                continue

            temp_c, temp_source = self._resolve_zone_temperature(zone_id, humidity_entity_id)
            if temp_c is None:
                continue

            reading = self._build_reading(zone_id, humidity_entity_id, temp_c, temp_source, now)
            if reading is not None:
                readings.append(reading)

        return readings

    def _scan_extra_sensors(self, now: datetime) -> list[SourceReading]:
        """Build readings for configured non-zone humidity/temperature pairs."""
        readings: list[SourceReading] = []
        for pair in self._extra_sensors:
            humidity_entity_id = pair.get("humidity")
            temperature_entity_id = pair.get("temperature")
            if not humidity_entity_id or not temperature_entity_id:
                continue

            temp_c = self._read_numeric_state(temperature_entity_id)
            if temp_c is None or not self._temp_plausible(temp_c):
                self._warn_once(
                    f"extra_temp:{temperature_entity_id}",
                    "Water temp control: temperature %s is missing or implausible (%s) — "
                    "dropping source %s",
                    temperature_entity_id,
                    temp_c,
                    humidity_entity_id,
                )
                continue

            reading = self._build_reading(
                f"extra:{humidity_entity_id}",
                humidity_entity_id,
                temp_c,
                TEMP_SOURCE_ENTITY,
                now,
            )
            if reading is not None:
                readings.append(reading)

        return readings

    def _zone_humidity_paused(self, zone_data: dict[str, Any]) -> bool:
        """Return True when the zone's HumidityDetector is PAUSED/STABILIZING.

        Read from the climate entity's ``status`` attribute rather than the
        detector object so the scanner stays a pure ``hass.states`` consumer.
        """
        climate_entity_id = zone_data.get("climate_entity_id")
        if not climate_entity_id:
            return False
        state = self._hass.states.get(climate_entity_id)
        if state is None:
            return False
        status = state.attributes.get("status") or {}
        for override in status.get("overrides", []) or []:
            if override.get("type") == "humidity":
                return True
        return False

    # ── temperature pairing ──────────────────────────────────────────────────

    def _resolve_zone_temperature(self, zone_id: str, humidity_entity_id: str) -> tuple[float | None, str]:
        """Resolve a co-located temperature for a zone humidity sensor.

        Order: (1) a temperature entity on the same device as the humidity
        sensor, (2) the zone climate entity's ``current_temperature``.  Pairing
        RH with a differently-placed temperature can eat the entire dew point
        margin, so the device match is strongly preferred.
        """
        paired_entity_id = self._find_paired_temp_entity(humidity_entity_id)
        if paired_entity_id is not None:
            temp_c = self._read_numeric_state(paired_entity_id)
            if temp_c is not None and self._temp_plausible(temp_c):
                return temp_c, TEMP_SOURCE_DEVICE

        temp_c = self._coordinator.get_zone_current_temp(zone_id)
        if temp_c is not None and self._temp_plausible(temp_c):
            if zone_id not in self._temp_source_logged:
                self._temp_source_logged.add(zone_id)
                _LOGGER.info(
                    "Water temp control: zone %s pairs humidity %s with the zone's "
                    "current_temperature (no temperature entity on the same device)",
                    zone_id,
                    humidity_entity_id,
                )
            return temp_c, TEMP_SOURCE_CLIMATE

        self._warn_once(
            f"zone_temp:{zone_id}",
            "Water temp control: no plausible temperature for zone %s — dropping it from the scan",
            zone_id,
        )
        return None, TEMP_SOURCE_CLIMATE

    def _find_paired_temp_entity(self, humidity_entity_id: str) -> str | None:
        """Return a temperature sensor on the same device, if the registry knows one."""
        if er is None:
            return None
        try:
            registry = er.async_get(self._hass)
            entry = registry.async_get(humidity_entity_id)
            if entry is None or entry.device_id is None:
                return None
            for sibling in er.async_entries_for_device(registry, entry.device_id):
                if sibling.entity_id == humidity_entity_id or sibling.domain != "sensor":
                    continue
                device_class = sibling.device_class or sibling.original_device_class
                if device_class == "temperature":
                    return sibling.entity_id
        except (AttributeError, KeyError, TypeError):
            # HA boundary: registry shape varies across versions and is mocked in tests.
            return None
        return None

    # ── reading construction ─────────────────────────────────────────────────

    def _build_reading(
        self,
        key: str,
        humidity_entity_id: str,
        temp_c: float,
        temp_source: str,
        now: datetime,
    ) -> SourceReading | None:
        """Resolve RH for one source and compute its dew point."""
        rh_pct, real = self._resolve_humidity(key, humidity_entity_id, now)
        try:
            dew_point_c = dew_point(temp_c, rh_pct)
        except ValueError:
            self._warn_once(
                f"dewpoint:{key}",
                "Water temp control: cannot compute dew point for %s (temp=%.1f, rh=%.1f)",
                key,
                temp_c,
                rh_pct,
            )
            return None

        return SourceReading(
            key=key,
            rh_pct=rh_pct,
            temp_c=temp_c,
            dew_point_c=dew_point_c,
            real=real,
            temp_source=temp_source,
        )

    def _resolve_humidity(self, key: str, humidity_entity_id: str, now: datetime) -> tuple[float, bool]:
        """Return the effective RH for a source and whether it is a real reading."""
        state = self._hass.states.get(humidity_entity_id)
        if state is None:
            return self._degraded_humidity(key), False

        if self._is_stale(state, now):
            self._warn_once(
                f"stale:{key}",
                "Water temp control: humidity %s is stale — using max(last EMA, fallback)",
                humidity_entity_id,
            )
            return self._degraded_humidity(key), False

        raw = self._to_float(state.state)
        if raw is None or not (WATER_TEMP_RH_MIN <= raw <= WATER_TEMP_RH_MAX):
            self._warn_once(
                f"implausible:{key}",
                "Water temp control: humidity %s reads %s (outside %.0f-%.0f%%) — using fallback %.0f%%",
                humidity_entity_id,
                state.state,
                WATER_TEMP_RH_MIN,
                WATER_TEMP_RH_MAX,
                self._fallback_humidity,
            )
            return self._degraded_humidity(key), False

        return self._update_ema(key, raw, now), True

    def _degraded_humidity(self, key: str) -> float:
        """RH to use when a source has no usable reading.

        ``max(last_ema, fallback)`` so a known-humid zone is not optimistically
        forgotten when its sensor goes quiet.
        """
        last_ema = self._ema.get(key)
        if last_ema is None:
            return self._fallback_humidity
        return max(last_ema, self._fallback_humidity)

    def _update_ema(self, key: str, raw_rh: float, now: datetime) -> float:
        """Advance the per-source RH EMA and return the smoothed value."""
        previous = self._ema.get(key)
        last_updated = self._ema_updated.get(key)
        if previous is None or last_updated is None:
            self._ema[key] = raw_rh
            self._ema_updated[key] = now
            return raw_rh

        dt_minutes = max(0.0, (now - last_updated).total_seconds() / 60.0)
        alpha = 1.0 - math.exp(-dt_minutes / self._ema_window_minutes) if self._ema_window_minutes > 0 else 1.0
        smoothed = previous + alpha * (raw_rh - previous)
        self._ema[key] = smoothed
        self._ema_updated[key] = now
        return smoothed

    # ── small helpers ────────────────────────────────────────────────────────

    def _is_stale(self, state: Any, now: datetime) -> bool:
        """Return True when the state's last_updated is older than the threshold."""
        last_updated = getattr(state, "last_updated", None)
        if last_updated is None:
            return False
        try:
            age_minutes = (now - last_updated).total_seconds() / 60.0
        except TypeError:
            return False
        return age_minutes > self._stale_after_minutes

    def _read_numeric_state(self, entity_id: str) -> float | None:
        """Read an entity's state as a float, or None."""
        state = self._hass.states.get(entity_id)
        if state is None:
            return None
        return self._to_float(state.state)

    @staticmethod
    def _to_float(value: Any) -> float | None:
        """Coerce a state value to float, or None."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _temp_plausible(temp_c: float) -> bool:
        """Return True when an air temperature is inside the plausible band."""
        return WATER_TEMP_AIR_TEMP_MIN <= temp_c <= WATER_TEMP_AIR_TEMP_MAX

    def _warn_once(self, key: str, message: str, *args: Any) -> None:
        """Emit a WARNING at most once per WATER_TEMP_WARN_INTERVAL_SECONDS per key."""
        from homeassistant.util import dt as dt_util

        now = dt_util.utcnow()
        last = self._last_warned.get(key)
        if last is not None and (now - last).total_seconds() < WATER_TEMP_WARN_INTERVAL_SECONDS:
            return
        self._last_warned[key] = now
        _LOGGER.warning(message, *args)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_water_temp_sources.py -v`
Expected: PASS — all tests green

- [ ] **Step 5: Lint and typecheck**

Run: `ruff check custom_components/adaptive_climate/managers/water_temp_sources.py tests/test_water_temp_sources.py && ruff format --check custom_components/adaptive_climate/managers/water_temp_sources.py && pyright custom_components/adaptive_climate/managers/water_temp_sources.py`
Expected: no findings

- [ ] **Step 6: Commit**

```bash
git add custom_components/adaptive_climate/managers/water_temp_sources.py tests/test_water_temp_sources.py
git commit -m "feat(watertemp): add dew point source scanner with EMA and guards"
```

---

### Task 6: WaterTempController — targets and ramps

**Files:**
- Create: `custom_components/adaptive_climate/managers/water_temp_controller.py`
- Test: `tests/test_water_temp_controller.py`

**Interfaces:**
- Consumes: `DewPointScanner` / `DewPointScan` (Task 5), water-temp constants (Task 2), `coordinator.get_zones_in_mode` (Task 4).
- Produces:
  - `ModeRampState` dataclass: `last_active: datetime | None`, `ramp_started: datetime | None`, `ramp_start_value: float | None`.
  - `WaterTempController(hass, coordinator, config, supply_temperature=None)`.
  - `controller.compute_targets(now: datetime) -> dict[str, float]` — mode key -> effective supply temp, for active modes only. Sets `controller.binding` and `controller.ramp_state`.
  - `controller.get_state_for_persistence() -> dict[str, Any]` / `controller.restore_state(state: dict[str, Any] | None) -> None` / `controller.mark_restored() -> None` / `controller.restored -> bool`.
  - `controller.effective_cooling_supply_temp -> float | None`.
  - Attributes used by later tasks: `_ramp: dict[str, ModeRampState]`, `_binding: dict[str, str]`, `_effective: dict[str, float]`, `_last_scan: DewPointScan | None`, `_cooling`/`_heating` config dicts, `_idle_days`, `_min_write_interval`, `_condensation_sensor`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_water_temp_controller.py`:

```python
"""Tests for WaterTempController: targets, ramps, writes, interlocks, gate."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.adaptive_climate.const import (
    WATER_TEMP_BINDING_BLIND,
    WATER_TEMP_BINDING_DEW_POINT,
    WATER_TEMP_BINDING_MIN_SUPPLY,
    WATER_TEMP_BINDING_RAMP,
    WATER_TEMP_BINDING_TARGET,
    WATER_TEMP_MODE_COOLING,
    WATER_TEMP_MODE_HEATING,
)
from custom_components.adaptive_climate.managers.water_temp_controller import (
    WaterTempController,
)
from custom_components.adaptive_climate.managers.water_temp_sources import DewPointScan

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

COOL_ENTITY = "number.hp_cool_supply"
HEAT_ENTITY = "number.hp_heat_supply"


def cooling_config(**overrides):
    config = {
        "target_entity": COOL_ENTITY,
        "min_supply_temp": 18.0,
        "dew_point_margin": 2.0,
        "fallback_humidity": 65.0,
        "ramp_start": 22.0,
        "ramp_rate": 1.0,
        "extra_sensors": [],
    }
    config.update(overrides)
    return config


def heating_config(**overrides):
    config = {
        "target_entity": HEAT_ENTITY,
        "target": 35.0,
        "ramp_start": 25.0,
        "ramp_rate": 2.0,
    }
    config.update(overrides)
    return config


def number_state(value, *, step=0.5, minimum=15.0, maximum=45.0):
    state = MagicMock()
    state.state = str(value)
    state.attributes = {"step": step, "min": minimum, "max": maximum}
    return state


def climate_state(mode, overrides=None):
    state = MagicMock()
    state.state = mode
    state.attributes = {"status": {"overrides": overrides or []}}
    return state


def build_controller(*, cooling=None, heating=None, zones_in_mode=None, states=None, **top_level):
    """Construct a controller with the scanner stubbed out."""
    hass = MagicMock()
    hass.states.get = (states or {}).get
    hass.services.async_call = AsyncMock(return_value=None)

    coordinator = MagicMock()
    zones_in_mode = zones_in_mode or {}
    coordinator.get_zones_in_mode = lambda mode: zones_in_mode.get(mode, {})

    config = {"idle_days": 7, "min_write_interval": 1800}
    config.update(top_level)
    if cooling is not None:
        config["cooling"] = cooling
    if heating is not None:
        config["heating"] = heating

    controller = WaterTempController(hass, coordinator, config)
    controller.mark_restored()
    return controller


def stub_scan(controller, dew_point=None, *, blind=False, worst_source="living"):
    controller._scanner = MagicMock()
    controller._scanner.scan = MagicMock(
        return_value=DewPointScan(
            dew_point=dew_point,
            worst_source=worst_source,
            blind=blind,
            readings=(),
        )
    )


# =============================================================================
# Targets
# =============================================================================


class TestCoolingTarget:
    def test_dew_point_plus_margin(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(20.0)},
        )
        stub_scan(controller, dew_point=17.0)

        targets = controller.compute_targets(NOW)

        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(19.0)
        assert controller.binding[WATER_TEMP_MODE_COOLING] == WATER_TEMP_BINDING_DEW_POINT

    def test_min_supply_temp_floors_the_target(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(20.0)},
        )
        stub_scan(controller, dew_point=10.0)

        targets = controller.compute_targets(NOW)

        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(18.0)
        assert controller.binding[WATER_TEMP_MODE_COOLING] == WATER_TEMP_BINDING_MIN_SUPPLY

    def test_blind_mode_floors_at_twenty(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(20.0)},
        )
        stub_scan(controller, dew_point=14.0, blind=True)

        targets = controller.compute_targets(NOW)

        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(20.0)
        assert controller.binding[WATER_TEMP_MODE_COOLING] == WATER_TEMP_BINDING_BLIND

    def test_blind_mode_respects_a_higher_min_supply_temp(self):
        controller = build_controller(
            cooling=cooling_config(min_supply_temp=24.0),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(26.0)},
        )
        stub_scan(controller, dew_point=None, blind=True)

        targets = controller.compute_targets(NOW)

        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(24.0)

    def test_no_cool_zones_means_no_cooling_target(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=17.0)

        assert WATER_TEMP_MODE_COOLING not in controller.compute_targets(NOW)


class TestHeatingTarget:
    def test_configured_target_is_used(self):
        controller = build_controller(
            heating=heating_config(),
            zones_in_mode={"heat": {"living": {}}},
            states={HEAT_ENTITY: number_state(35.0)},
        )
        controller._ramp[WATER_TEMP_MODE_HEATING].last_active = NOW - timedelta(hours=1)

        targets = controller.compute_targets(NOW)

        assert targets[WATER_TEMP_MODE_HEATING] == pytest.approx(35.0)
        assert controller.binding[WATER_TEMP_MODE_HEATING] == WATER_TEMP_BINDING_TARGET

    def test_target_falls_back_to_supply_temperature(self):
        hass = MagicMock()
        hass.states.get = {HEAT_ENTITY: number_state(40.0)}.get
        hass.services.async_call = AsyncMock(return_value=None)
        coordinator = MagicMock()
        coordinator.get_zones_in_mode = lambda mode: {"living": {}} if mode == "heat" else {}

        controller = WaterTempController(
            hass,
            coordinator,
            {"heating": {k: v for k, v in heating_config().items() if k != "target"}},
            supply_temperature=40.0,
        )
        controller.mark_restored()
        controller._ramp[WATER_TEMP_MODE_HEATING].last_active = NOW - timedelta(hours=1)

        assert controller.compute_targets(NOW)[WATER_TEMP_MODE_HEATING] == pytest.approx(40.0)

    def test_no_heat_zones_means_no_heating_target(self):
        controller = build_controller(
            heating=heating_config(),
            zones_in_mode={"heat": {}},
            states={HEAT_ENTITY: number_state(35.0)},
        )
        assert WATER_TEMP_MODE_HEATING not in controller.compute_targets(NOW)


# =============================================================================
# Ramps
# =============================================================================


class TestRamps:
    def test_first_run_starts_a_ramp(self):
        """No persisted state is treated as long-idle: conservative both ways."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0)

        targets = controller.compute_targets(NOW)

        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(22.0)
        assert controller.binding[WATER_TEMP_MODE_COOLING] == WATER_TEMP_BINDING_RAMP
        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started == NOW

    def test_cooling_ramp_descends_at_the_configured_rate(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0)
        controller.compute_targets(NOW)

        assert controller.compute_targets(NOW + timedelta(days=2))[WATER_TEMP_MODE_COOLING] == pytest.approx(20.0)

    def test_cooling_ramp_ends_when_it_reaches_the_dew_target(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0)
        controller.compute_targets(NOW)

        later = controller.compute_targets(NOW + timedelta(days=10))

        assert later[WATER_TEMP_MODE_COOLING] == pytest.approx(18.0)
        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started is None

    def test_heating_ramp_ascends_and_ends_at_target(self):
        controller = build_controller(
            heating=heating_config(),
            zones_in_mode={"heat": {"living": {}}},
            states={HEAT_ENTITY: number_state(25.0)},
        )
        controller.compute_targets(NOW)

        assert controller.compute_targets(NOW + timedelta(days=2))[WATER_TEMP_MODE_HEATING] == pytest.approx(29.0)
        assert controller.compute_targets(NOW + timedelta(days=10))[WATER_TEMP_MODE_HEATING] == pytest.approx(35.0)
        assert controller.ramp_state[WATER_TEMP_MODE_HEATING].ramp_started is None

    def test_heating_ramp_seeds_from_the_entity_when_it_runs_hotter(self):
        """A system already at 33 degC must not be yanked down to 25 (backup heater trap)."""
        controller = build_controller(
            heating=heating_config(),
            zones_in_mode={"heat": {"living": {}}},
            states={HEAT_ENTITY: number_state(33.0)},
        )

        assert controller.compute_targets(NOW)[WATER_TEMP_MODE_HEATING] == pytest.approx(33.0)
        assert controller.ramp_state[WATER_TEMP_MODE_HEATING].ramp_start_value == pytest.approx(33.0)

    def test_cooling_ramp_never_seeds_from_the_entity(self):
        """Seeding cooling from a cold entity would start too cold on a warm slab."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(16.0)},
        )
        stub_scan(controller, dew_point=14.0)

        assert controller.compute_targets(NOW)[WATER_TEMP_MODE_COOLING] == pytest.approx(22.0)

    def test_idle_shorter_than_idle_days_does_not_restart_a_ramp(self):
        """Shoulder-season HEAT/COOL flips must not restart the ramp."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(18.0)},
        )
        stub_scan(controller, dew_point=14.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(days=3)

        targets = controller.compute_targets(NOW)

        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started is None
        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(18.0)

    def test_idle_beyond_idle_days_restarts_the_ramp(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(18.0)},
        )
        stub_scan(controller, dew_point=14.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(days=30)

        targets = controller.compute_targets(NOW)

        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started == NOW
        assert targets[WATER_TEMP_MODE_COOLING] == pytest.approx(22.0)

    def test_in_progress_ramp_continues_from_its_own_start_time(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0)
        controller.compute_targets(NOW)
        started = controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started

        controller.compute_targets(NOW + timedelta(days=1))

        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started == started

    def test_heating_and_cooling_ramps_are_independent(self):
        controller = build_controller(
            cooling=cooling_config(),
            heating=heating_config(),
            zones_in_mode={"cool": {"living": {}}, "heat": {}},
            states={COOL_ENTITY: number_state(22.0), HEAT_ENTITY: number_state(35.0)},
        )
        stub_scan(controller, dew_point=14.0)

        controller.compute_targets(NOW)

        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started == NOW
        assert controller.ramp_state[WATER_TEMP_MODE_HEATING].ramp_started is None


# =============================================================================
# Persistence round-trip
# =============================================================================


class TestPersistenceState:
    def test_state_round_trips_through_iso_strings(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0)
        controller.compute_targets(NOW)

        state = controller.get_state_for_persistence()
        assert state[WATER_TEMP_MODE_COOLING]["ramp_started"] == NOW.isoformat()

        restored = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        restored.restore_state(state)

        assert restored.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started == NOW

    def test_future_ramp_start_is_clamped_to_now_on_restore(self):
        """Clock corrections must never yield a negative elapsed time."""
        controller = build_controller(cooling=cooling_config())
        future = (NOW + timedelta(days=400)).isoformat()

        controller.restore_state({WATER_TEMP_MODE_COOLING: {"ramp_started": future, "last_active": future}})

        ramp = controller.ramp_state[WATER_TEMP_MODE_COOLING]
        assert ramp.ramp_started is not None
        assert ramp.ramp_started <= controller._utcnow()

    def test_restore_tolerates_missing_and_malformed_entries(self):
        controller = build_controller(cooling=cooling_config())

        controller.restore_state(None)
        controller.restore_state({WATER_TEMP_MODE_COOLING: {"ramp_started": "not-a-date"}})

        assert controller.ramp_state[WATER_TEMP_MODE_COOLING].ramp_started is None
        assert controller.restored is True

    def test_compute_is_skipped_until_state_is_restored(self):
        hass = MagicMock()
        hass.states.get = {COOL_ENTITY: number_state(22.0)}.get
        coordinator = MagicMock()
        coordinator.get_zones_in_mode = lambda mode: {"living": {}} if mode == "cool" else {}

        controller = WaterTempController(hass, coordinator, {"cooling": cooling_config()})
        stub_scan(controller, dew_point=14.0)

        assert controller.compute_targets(NOW) == {}
        assert controller.restored is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_water_temp_controller.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '...managers.water_temp_controller'`

- [ ] **Step 3: Write minimal implementation**

Create `custom_components/adaptive_climate/managers/water_temp_controller.py`:

```python
"""Water temperature control: dew-point cooling, heating target, startup ramps.

Owns the effective supply-water temperature for each HVAC mode and pushes it to
external ``number`` / ``input_number`` entities consumed by the heat pump or
mixing valve.  Named ``*Controller`` (matching ``heater_controller.py``) because
it actuates external hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

from ..const import (
    CONF_WATER_TEMP_COOLING,
    CONF_WATER_TEMP_DEW_POINT_MARGIN,
    CONF_WATER_TEMP_EXTRA_SENSORS,
    CONF_WATER_TEMP_FALLBACK_HUMIDITY,
    CONF_WATER_TEMP_HEATING,
    CONF_WATER_TEMP_IDLE_DAYS,
    CONF_WATER_TEMP_MIN_SUPPLY_TEMP,
    CONF_WATER_TEMP_MIN_WRITE_INTERVAL,
    CONF_WATER_TEMP_CONDENSATION_SENSOR,
    CONF_WATER_TEMP_RAMP_RATE,
    CONF_WATER_TEMP_RAMP_START,
    CONF_WATER_TEMP_TARGET,
    CONF_WATER_TEMP_TARGET_ENTITY,
    DEFAULT_WATER_TEMP_COOLING_RAMP_RATE,
    DEFAULT_WATER_TEMP_COOLING_RAMP_START,
    DEFAULT_WATER_TEMP_DEW_POINT_MARGIN,
    DEFAULT_WATER_TEMP_FALLBACK_HUMIDITY,
    DEFAULT_WATER_TEMP_HEATING_RAMP_RATE,
    DEFAULT_WATER_TEMP_HEATING_RAMP_START,
    DEFAULT_WATER_TEMP_IDLE_DAYS,
    DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP,
    DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL,
    WATER_TEMP_BINDING_BLIND,
    WATER_TEMP_BINDING_DEW_POINT,
    WATER_TEMP_BINDING_MIN_SUPPLY,
    WATER_TEMP_BINDING_RAMP,
    WATER_TEMP_BINDING_TARGET,
    WATER_TEMP_BLIND_MIN_SUPPLY,
    WATER_TEMP_MODE_COOLING,
    WATER_TEMP_MODE_HEATING,
)
from .water_temp_sources import DewPointScan, DewPointScanner

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..coordinator import AdaptiveThermostatCoordinator

_LOGGER = logging.getLogger(__name__)

_SECONDS_PER_DAY = 86400.0

MODE_HVAC_STATE = {
    WATER_TEMP_MODE_COOLING: "cool",
    WATER_TEMP_MODE_HEATING: "heat",
}


@dataclass
class ModeRampState:
    """Idle / ramp bookkeeping for one mode.

    All timestamps are wall-clock ``dt_util.utcnow()`` values persisted as ISO
    strings — never ``time.monotonic()``, which resets on restart.
    """

    last_active: datetime | None = None
    ramp_started: datetime | None = None
    ramp_start_value: float | None = None


class WaterTempController:
    """Compute and write supply water temperature setpoints."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: AdaptiveThermostatCoordinator,
        config: dict[str, Any],
        supply_temperature: float | None = None,
    ) -> None:
        """Initialize the controller.

        Args:
            hass: Home Assistant instance.
            coordinator: Zone registry, used for per-mode zone lookups.
            config: The validated ``water_temp_control`` sub-dict.
            supply_temperature: Domain-level ``supply_temperature``, the fallback
                for ``heating.target``.  Passed in rather than read from
                ``hass.data`` because the coordinator is constructed before
                ``hass.data[DOMAIN]["supply_temperature"]`` is written.
        """
        self.hass = hass
        self._coordinator = coordinator

        self._idle_days = float(config.get(CONF_WATER_TEMP_IDLE_DAYS, DEFAULT_WATER_TEMP_IDLE_DAYS))
        self._min_write_interval = float(
            config.get(CONF_WATER_TEMP_MIN_WRITE_INTERVAL, DEFAULT_WATER_TEMP_MIN_WRITE_INTERVAL)
        )
        self._condensation_sensor: str | None = config.get(CONF_WATER_TEMP_CONDENSATION_SENSOR)

        self._cooling: dict[str, Any] | None = config.get(CONF_WATER_TEMP_COOLING)
        self._heating: dict[str, Any] | None = config.get(CONF_WATER_TEMP_HEATING)

        self._heating_target: float | None = None
        if self._heating is not None:
            configured = self._heating.get(CONF_WATER_TEMP_TARGET)
            self._heating_target = float(configured) if configured is not None else (
                float(supply_temperature) if supply_temperature is not None else None
            )

        self._scanner: DewPointScanner | None = None
        if self._cooling is not None:
            self._scanner = DewPointScanner(
                hass,
                coordinator,
                extra_sensors=self._cooling.get(CONF_WATER_TEMP_EXTRA_SENSORS, []) or [],
                fallback_humidity=float(
                    self._cooling.get(CONF_WATER_TEMP_FALLBACK_HUMIDITY, DEFAULT_WATER_TEMP_FALLBACK_HUMIDITY)
                ),
            )

        self._ramp: dict[str, ModeRampState] = {
            WATER_TEMP_MODE_COOLING: ModeRampState(),
            WATER_TEMP_MODE_HEATING: ModeRampState(),
        }
        self._binding: dict[str, str] = {}
        self._effective: dict[str, float] = {}
        self._last_scan: DewPointScan | None = None
        self._restored = False

    # ── introspection ────────────────────────────────────────────────────────

    @property
    def enabled_modes(self) -> tuple[str, ...]:
        """Return the configured mode keys."""
        modes = []
        if self._cooling is not None:
            modes.append(WATER_TEMP_MODE_COOLING)
        if self._heating is not None:
            modes.append(WATER_TEMP_MODE_HEATING)
        return tuple(modes)

    @property
    def ramp_state(self) -> dict[str, ModeRampState]:
        """Return the per-mode ramp state (read-only use)."""
        return self._ramp

    @property
    def binding(self) -> dict[str, str]:
        """Return the per-mode binding constraint from the last computation."""
        return self._binding

    @property
    def restored(self) -> bool:
        """Return True once persisted state has been applied (or found absent)."""
        return self._restored

    @property
    def effective_cooling_supply_temp(self) -> float | None:
        """Return the current effective cooling supply temp, or None."""
        return self._effective.get(WATER_TEMP_MODE_COOLING)

    @staticmethod
    def _utcnow() -> datetime:
        """Return current wall-clock UTC (indirection keeps tests deterministic)."""
        return dt_util.utcnow()

    # ── persistence ──────────────────────────────────────────────────────────

    def get_state_for_persistence(self) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of ramp and write state."""
        state: dict[str, Any] = {}
        for mode, ramp in self._ramp.items():
            state[mode] = {
                "last_active": ramp.last_active.isoformat() if ramp.last_active else None,
                "ramp_started": ramp.ramp_started.isoformat() if ramp.ramp_started else None,
                "ramp_start_value": ramp.ramp_start_value,
            }
        state["last_written"] = dict(getattr(self, "_last_written", {}))
        return state

    def restore_state(self, state: dict[str, Any] | None) -> None:
        """Restore ramp and write state from persistence.

        Guards against clock corrections by clamping any future timestamp to
        "now" — a persisted ``ramp_started`` in the future would otherwise
        produce a negative elapsed time.

        Args:
            state: Previously persisted dict, or None on first run.
        """
        if state:
            now = self._utcnow()
            for mode in (WATER_TEMP_MODE_COOLING, WATER_TEMP_MODE_HEATING):
                mode_state = state.get(mode) or {}
                ramp = self._ramp[mode]
                ramp.last_active = self._parse_timestamp(mode_state.get("last_active"), now)
                ramp.ramp_started = self._parse_timestamp(mode_state.get("ramp_started"), now)
                value = mode_state.get("ramp_start_value")
                ramp.ramp_start_value = float(value) if isinstance(value, (int, float)) else None

            last_written = state.get("last_written")
            if isinstance(last_written, dict):
                self._last_written = {
                    entity_id: float(value)
                    for entity_id, value in last_written.items()
                    if isinstance(value, (int, float))
                }

        self.mark_restored()

    def mark_restored(self) -> None:
        """Mark state as restored so computation may begin."""
        self._restored = True

    @staticmethod
    def _parse_timestamp(value: Any, now: datetime) -> datetime | None:
        """Parse an ISO timestamp, clamping future values to ``now``."""
        if not isinstance(value, str):
            return None
        parsed = dt_util.parse_datetime(value)
        if parsed is None:
            return None
        return min(parsed, now)

    # ── computation ──────────────────────────────────────────────────────────

    def compute_targets(self, now: datetime) -> dict[str, float]:
        """Compute the effective supply temperature for every active mode.

        Args:
            now: Current wall-clock time.

        Returns:
            Mapping of mode key -> effective supply temperature in °C.  Modes
            that are not configured or have no zones in that mode are absent.
        """
        if not self._restored:
            _LOGGER.debug("Water temp control: state not restored yet, skipping computation")
            return {}

        targets: dict[str, float] = {}
        self._last_scan = None

        if self._cooling is not None:
            value = self._compute_cooling(now)
            if value is not None:
                targets[WATER_TEMP_MODE_COOLING] = value

        if self._heating is not None:
            value = self._compute_heating(now)
            if value is not None:
                targets[WATER_TEMP_MODE_HEATING] = value

        self._effective = dict(targets)
        return targets

    def _compute_cooling(self, now: datetime) -> float | None:
        """Compute the effective cooling supply temperature, or None if inactive."""
        if not self._mode_is_active(WATER_TEMP_MODE_COOLING):
            return None

        cooling = self._cooling or {}
        min_supply = float(cooling.get(CONF_WATER_TEMP_MIN_SUPPLY_TEMP, DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP))
        margin = float(cooling.get(CONF_WATER_TEMP_DEW_POINT_MARGIN, DEFAULT_WATER_TEMP_DEW_POINT_MARGIN))

        scan = self._scanner.scan(now) if self._scanner is not None else None
        self._last_scan = scan

        if scan is None or scan.blind or scan.dew_point is None:
            dew_target = max(min_supply, WATER_TEMP_BLIND_MIN_SUPPLY)
            binding = WATER_TEMP_BINDING_BLIND
        else:
            with_margin = scan.dew_point + margin
            if with_margin >= min_supply:
                dew_target, binding = with_margin, WATER_TEMP_BINDING_DEW_POINT
            else:
                dew_target, binding = min_supply, WATER_TEMP_BINDING_MIN_SUPPLY

        self._update_ramp(WATER_TEMP_MODE_COOLING, now, seed_from_entity=False)
        ramp = self._ramp[WATER_TEMP_MODE_COOLING]

        if ramp.ramp_started is not None and ramp.ramp_start_value is not None:
            rate = float(cooling.get(CONF_WATER_TEMP_RAMP_RATE, DEFAULT_WATER_TEMP_COOLING_RAMP_RATE))
            ramp_value = ramp.ramp_start_value - rate * self._days_since(ramp.ramp_started, now)
            if ramp_value > dew_target:
                self._binding[WATER_TEMP_MODE_COOLING] = WATER_TEMP_BINDING_RAMP
                return ramp_value
            self._end_ramp(WATER_TEMP_MODE_COOLING)

        self._binding[WATER_TEMP_MODE_COOLING] = binding
        return dew_target

    def _compute_heating(self, now: datetime) -> float | None:
        """Compute the effective heating supply temperature, or None if inactive."""
        if not self._mode_is_active(WATER_TEMP_MODE_HEATING):
            return None
        if self._heating_target is None:
            _LOGGER.warning("Water temp control: heating configured without a resolvable target")
            return None

        self._update_ramp(WATER_TEMP_MODE_HEATING, now, seed_from_entity=True)
        ramp = self._ramp[WATER_TEMP_MODE_HEATING]
        heating = self._heating or {}

        if ramp.ramp_started is not None and ramp.ramp_start_value is not None:
            rate = float(heating.get(CONF_WATER_TEMP_RAMP_RATE, DEFAULT_WATER_TEMP_HEATING_RAMP_RATE))
            ramp_value = ramp.ramp_start_value + rate * self._days_since(ramp.ramp_started, now)
            if ramp_value < self._heating_target:
                self._binding[WATER_TEMP_MODE_HEATING] = WATER_TEMP_BINDING_RAMP
                return ramp_value
            self._end_ramp(WATER_TEMP_MODE_HEATING)

        self._binding[WATER_TEMP_MODE_HEATING] = WATER_TEMP_BINDING_TARGET
        return self._heating_target

    # ── ramp lifecycle ───────────────────────────────────────────────────────

    def _update_ramp(self, mode: str, now: datetime, seed_from_entity: bool) -> None:
        """Start a ramp when the mode resumes after >= idle_days inactive."""
        ramp = self._ramp[mode]

        if ramp.last_active is None:
            idle_days = float("inf")  # first run: treat as long-idle, ramp conservatively
        else:
            idle_days = max(0.0, self._days_since(ramp.last_active, now))

        if ramp.ramp_started is None and idle_days >= self._idle_days:
            ramp.ramp_started = now
            ramp.ramp_start_value = self._seed_ramp_start(mode, seed_from_entity)
            _LOGGER.info(
                "Water temp control: starting %s ramp from %.1f°C (idle for %.1f days)",
                mode,
                ramp.ramp_start_value,
                idle_days if idle_days != float("inf") else -1.0,
            )

        ramp.last_active = now

    def _seed_ramp_start(self, mode: str, seed_from_entity: bool) -> float:
        """Return the value a new ramp starts from.

        Heating seeds from ``max(configured ramp_start, current entity value)``
        so a system already running hot is never yanked down (backup-heater
        trap).  Cooling always uses the configured ``ramp_start`` — seeding from
        the entity would start too cold on a warm slab.
        """
        config = self._heating if mode == WATER_TEMP_MODE_HEATING else self._cooling
        default = (
            DEFAULT_WATER_TEMP_HEATING_RAMP_START
            if mode == WATER_TEMP_MODE_HEATING
            else DEFAULT_WATER_TEMP_COOLING_RAMP_START
        )
        configured = float((config or {}).get(CONF_WATER_TEMP_RAMP_START, default))

        if not seed_from_entity:
            return configured

        current = self._read_entity_value(self._target_entity(mode))
        if current is None:
            return configured
        return max(configured, current)

    def _end_ramp(self, mode: str) -> None:
        """Clear ramp state once the ramp bound stops binding."""
        ramp = self._ramp[mode]
        if ramp.ramp_started is not None:
            _LOGGER.info("Water temp control: %s ramp complete", mode)
        ramp.ramp_started = None
        ramp.ramp_start_value = None

    @staticmethod
    def _days_since(start: datetime, now: datetime) -> float:
        """Return elapsed days, clamped at >= 0 to survive clock corrections."""
        return max(0.0, (now - start).total_seconds() / _SECONDS_PER_DAY)

    # ── entity helpers ───────────────────────────────────────────────────────

    def _mode_is_active(self, mode: str) -> bool:
        """Return True when at least one zone's climate entity is in this mode."""
        return bool(self._coordinator.get_zones_in_mode(MODE_HVAC_STATE[mode]))

    def _target_entity(self, mode: str) -> str:
        """Return the configured target entity id for a mode."""
        config = self._heating if mode == WATER_TEMP_MODE_HEATING else self._cooling
        return str((config or {}).get(CONF_WATER_TEMP_TARGET_ENTITY, ""))

    def _read_entity_value(self, entity_id: str) -> float | None:
        """Read a number entity's current value as a float, or None."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None:
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_water_temp_controller.py -v`
Expected: PASS — all target, ramp and persistence-state tests green

- [ ] **Step 5: Lint and typecheck**

Run: `ruff check custom_components/adaptive_climate/managers/water_temp_controller.py tests/test_water_temp_controller.py && ruff format --check custom_components/adaptive_climate/managers/water_temp_controller.py && pyright custom_components/adaptive_climate/managers/water_temp_controller.py`
Expected: no findings

- [ ] **Step 6: Commit**

```bash
git add custom_components/adaptive_climate/managers/water_temp_controller.py tests/test_water_temp_controller.py
git commit -m "feat(watertemp): add controller targets and ramp lifecycle"
```

---

### Task 7: Write policy — safe rounding, clamping, asymmetric dwell, park

**Files:**
- Modify: `custom_components/adaptive_climate/managers/water_temp_controller.py`
- Test: `tests/test_water_temp_controller.py` (append)

**Interfaces:**
- Consumes: everything from Task 6.
- Produces:
  - `async controller.async_apply(now: datetime) -> None` — compute targets, write each mode's entity, park deactivated modes.
  - `async controller._async_write(mode, entity_id, value, *, now, force=False) -> bool` — returns True when a service call was issued.
  - `controller._last_written: dict[str, float]`, `controller._pending: dict[str, tuple[float, datetime]]`, `controller._gate_until: dict[str, datetime]`, `controller._was_active: dict[str, bool]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_water_temp_controller.py`:

```python
# =============================================================================
# Write policy
# =============================================================================


def written_values(controller):
    """Return the list of values passed to number.set_value."""
    return [call.args[2]["value"] for call in controller.hass.services.async_call.call_args_list]


def written_domains(controller):
    return [call.args[0] for call in controller.hass.services.async_call.call_args_list]


class TestWritePolicy:
    @pytest.mark.asyncio
    async def test_writes_the_computed_value_to_the_target_entity(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(20.0)},
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        controller.hass.services.async_call.assert_awaited_once()
        domain, service, payload = controller.hass.services.async_call.await_args.args[:3]
        assert (domain, service) == ("number", "set_value")
        assert payload == {"entity_id": COOL_ENTITY, "value": 19.0}

    @pytest.mark.asyncio
    async def test_input_number_entities_use_the_input_number_domain(self):
        entity = "input_number.hp_cool_supply"
        controller = build_controller(
            cooling=cooling_config(target_entity=entity),
            zones_in_mode={"cool": {"living": {}}},
            states={entity: number_state(20.0)},
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert written_domains(controller) == ["input_number"]

    @pytest.mark.asyncio
    async def test_cooling_rounds_up_to_the_entity_step(self):
        """Nearest-rounding would silently spend safety margin."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(20.0, step=0.5)},
        )
        stub_scan(controller, dew_point=17.1)  # 19.1 -> rounds up to 19.5
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert written_values(controller) == [19.5]

    @pytest.mark.asyncio
    async def test_heating_rounds_down_to_the_entity_step(self):
        controller = build_controller(
            heating=heating_config(target=35.3),
            zones_in_mode={"heat": {"living": {}}},
            states={HEAT_ENTITY: number_state(30.0, step=0.5)},
        )
        controller._ramp[WATER_TEMP_MODE_HEATING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert written_values(controller) == [35.0]

    @pytest.mark.asyncio
    async def test_missing_step_attribute_falls_back_to_half_a_degree(self):
        state = number_state(20.0)
        state.attributes = {"min": 15.0, "max": 45.0}
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: state},
        )
        stub_scan(controller, dew_point=17.1)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert written_values(controller) == [19.5]

    @pytest.mark.asyncio
    async def test_value_is_clamped_to_the_entity_min_and_max(self):
        controller = build_controller(
            cooling=cooling_config(min_supply_temp=5.0),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(20.0, minimum=16.0, maximum=30.0)},
        )
        stub_scan(controller, dew_point=8.0)  # 10.0, below the entity min
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert written_values(controller) == [16.0]

    @pytest.mark.asyncio
    async def test_out_of_range_value_is_not_rewritten_every_cycle(self):
        """Comparing pre-clamp values would re-issue identical calls forever."""
        controller = build_controller(
            cooling=cooling_config(min_supply_temp=5.0),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(20.0, minimum=16.0, maximum=30.0)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        stub_scan(controller, dew_point=8.0)
        await controller.async_apply(NOW)
        stub_scan(controller, dew_point=7.0)  # still clamps to 16.0
        await controller.async_apply(NOW + timedelta(minutes=5))

        assert written_values(controller) == [16.0]

    @pytest.mark.asyncio
    async def test_safe_direction_change_writes_immediately(self):
        """Cooling upward is the safe direction — no dwell required."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(19.0)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        stub_scan(controller, dew_point=17.0)
        await controller.async_apply(NOW)
        stub_scan(controller, dew_point=19.0)  # 21.0, upward
        await controller.async_apply(NOW + timedelta(minutes=5))

        assert written_values(controller) == [19.0, 21.0]

    @pytest.mark.asyncio
    async def test_unsafe_direction_change_requires_the_dwell_window(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(21.0)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        stub_scan(controller, dew_point=19.0)
        await controller.async_apply(NOW)  # writes 21.0
        stub_scan(controller, dew_point=17.0)  # 19.0, downward
        await controller.async_apply(NOW + timedelta(minutes=5))
        assert written_values(controller) == [21.0]  # held

        await controller.async_apply(NOW + timedelta(minutes=40))  # > 1800 s
        assert written_values(controller) == [21.0, 19.0]

    @pytest.mark.asyncio
    async def test_dwell_timer_restarts_when_the_pending_value_changes(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(21.0)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        stub_scan(controller, dew_point=19.0)
        await controller.async_apply(NOW)
        stub_scan(controller, dew_point=17.0)
        await controller.async_apply(NOW + timedelta(minutes=20))
        stub_scan(controller, dew_point=16.0)  # different pending value, timer restarts
        await controller.async_apply(NOW + timedelta(minutes=25))
        await controller.async_apply(NOW + timedelta(minutes=40))  # only 15 min on the new value

        assert written_values(controller) == [21.0]

    @pytest.mark.asyncio
    async def test_no_dither_at_a_step_boundary_under_rh_noise(self):
        """+-1% RH noise around a rounding boundary must produce one write."""
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(19.5)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        for index, dew in enumerate([17.24, 17.26, 17.24, 17.26, 17.25]):
            stub_scan(controller, dew_point=dew)
            await controller.async_apply(NOW + timedelta(minutes=5 * index))

        assert written_values(controller) == []  # all round up to 19.5, already written

    @pytest.mark.asyncio
    async def test_inactive_mode_is_never_written_after_parking(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=17.0)

        await controller.async_apply(NOW)
        await controller.async_apply(NOW + timedelta(minutes=5))

        assert written_values(controller) == []

    @pytest.mark.asyncio
    async def test_deactivation_parks_the_entity_at_ramp_start(self):
        """Never leave the most aggressive value latched for the next season."""
        zones = {"cool": {"living": {}}}
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode=zones,
            states={COOL_ENTITY: number_state(19.0)},
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)
        await controller.async_apply(NOW)

        zones["cool"] = {}
        await controller.async_apply(NOW + timedelta(minutes=5))

        assert written_values(controller) == [19.0, 22.0]

    @pytest.mark.asyncio
    async def test_park_happens_exactly_once(self):
        zones = {"cool": {"living": {}}}
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode=zones,
            states={COOL_ENTITY: number_state(19.0)},
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)
        await controller.async_apply(NOW)

        zones["cool"] = {}
        await controller.async_apply(NOW + timedelta(minutes=5))
        await controller.async_apply(NOW + timedelta(minutes=10))

        assert written_values(controller) == [19.0, 22.0]

    @pytest.mark.asyncio
    async def test_service_failure_is_logged_and_retried_next_cycle(self):
        from homeassistant.exceptions import HomeAssistantError

        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(21.0)},
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)
        controller.hass.services.async_call = AsyncMock(side_effect=HomeAssistantError("boom"))

        await controller.async_apply(NOW)
        assert controller._last_written.get(COOL_ENTITY) is None

        controller.hass.services.async_call = AsyncMock(return_value=None)
        await controller.async_apply(NOW + timedelta(minutes=5))
        assert controller._last_written[COOL_ENTITY] == pytest.approx(19.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_water_temp_controller.py::TestWritePolicy -v`
Expected: FAIL — `AttributeError: 'WaterTempController' object has no attribute 'async_apply'`

- [ ] **Step 3: Write minimal implementation**

In `custom_components/adaptive_climate/managers/water_temp_controller.py`, add to the const import block:

```python
    DEFAULT_WATER_TEMP_STEP,
    SUPPLY_TEMP_MAX,
    SUPPLY_TEMP_MIN,
    WATER_TEMP_GATE_WRITE_DELTA,
    WATER_TEMP_SETTLING_MINUTES,
```

and add near the other imports:

```python
import math
from datetime import timedelta

from homeassistant.exceptions import HomeAssistantError, ServiceNotFound

from .heater_service_caller import HeaterServiceCaller
```

Add these fields to `__init__` (after `self._restored = False`):

```python
        self._last_written: dict[str, float] = {}
        self._pending: dict[str, tuple[float, datetime]] = {}
        self._gate_until: dict[str, datetime] = {}
        self._was_active: dict[str, bool] = {
            WATER_TEMP_MODE_COOLING: False,
            WATER_TEMP_MODE_HEATING: False,
        }
        self._last_write_error: dict[str, datetime] = {}
```

Append these methods to the class:

```python
    # ── apply cycle ──────────────────────────────────────────────────────────

    async def async_apply(self, now: datetime) -> None:
        """Compute targets and push them to the configured entities.

        Args:
            now: Current wall-clock time.
        """
        targets = self.compute_targets(now)

        for mode in self.enabled_modes:
            entity_id = self._target_entity(mode)
            if not entity_id:
                continue

            value = targets.get(mode)
            if value is not None:
                self._was_active[mode] = True
                await self._async_write(mode, entity_id, value, now=now)
                continue

            if self._was_active[mode]:
                # Mode just deactivated: park at ramp_start rather than leaving
                # the most aggressive value latched for the next season.
                self._was_active[mode] = False
                park_value = self._park_value(mode)
                _LOGGER.info("Water temp control: %s deactivated, parking at %.1f°C", mode, park_value)
                await self._async_write(mode, entity_id, park_value, now=now, force=True)

    def _park_value(self, mode: str) -> float:
        """Return the configured ramp_start used as this mode's park value."""
        config = self._heating if mode == WATER_TEMP_MODE_HEATING else self._cooling
        default = (
            DEFAULT_WATER_TEMP_HEATING_RAMP_START
            if mode == WATER_TEMP_MODE_HEATING
            else DEFAULT_WATER_TEMP_COOLING_RAMP_START
        )
        return float((config or {}).get(CONF_WATER_TEMP_RAMP_START, default))

    # ── write policy ─────────────────────────────────────────────────────────

    async def _async_write(
        self,
        mode: str,
        entity_id: str,
        value: float,
        *,
        now: datetime,
        force: bool = False,
    ) -> bool:
        """Round, clamp and conditionally write a supply temperature.

        Args:
            mode: Mode key the value belongs to.
            entity_id: Target ``number`` / ``input_number`` entity.
            value: Unrounded, unclamped desired value in °C.
            now: Current wall-clock time.
            force: Bypass the unsafe-direction dwell (parks and interlocks).

        Returns:
            True when a service call was issued and accepted.
        """
        minimum, maximum, step = self._entity_limits(entity_id)
        final = min(max(self._round_safe(value, mode, step), minimum), maximum)

        last = self._last_written.get(entity_id)
        # Compare the post-clamp, post-round value: comparing the raw value
        # would re-issue identical calls forever when the target is out of range.
        if last is not None and abs(final - last) < 1e-6:
            self._pending.pop(entity_id, None)
            return False

        if not force and last is not None and not self._is_safe_direction(mode, final, last):
            pending = self._pending.get(entity_id)
            if pending is None or abs(pending[0] - final) > 1e-6:
                self._pending[entity_id] = (final, now)
                return False
            if (now - pending[1]).total_seconds() < self._min_write_interval:
                return False

        if not await self._async_call_set_value(entity_id, final, now):
            return False

        self._pending.pop(entity_id, None)
        if last is not None and abs(final - last) >= WATER_TEMP_GATE_WRITE_DELTA:
            self._gate_until[mode] = now + timedelta(minutes=WATER_TEMP_SETTLING_MINUTES)
        self._last_written[entity_id] = final
        return True

    @staticmethod
    def _is_safe_direction(mode: str, new_value: float, last_value: float) -> bool:
        """Return True when the change moves in the condensation-safe direction.

        Cooling: warmer water is safer (up).  Heating: cooler water is safer (down).
        """
        if mode == WATER_TEMP_MODE_COOLING:
            return new_value > last_value
        return new_value < last_value

    @staticmethod
    def _round_safe(value: float, mode: str, step: float) -> float:
        """Round to the entity step, always toward the safe side."""
        if step <= 0:
            return round(value, 3)
        if mode == WATER_TEMP_MODE_COOLING:
            return round(math.ceil(value / step - 1e-9) * step, 3)
        return round(math.floor(value / step + 1e-9) * step, 3)

    def _entity_limits(self, entity_id: str) -> tuple[float, float, float]:
        """Return the target entity's (min, max, step), with safe fallbacks."""
        state = self.hass.states.get(entity_id)
        if state is None:
            return SUPPLY_TEMP_MIN, SUPPLY_TEMP_MAX, DEFAULT_WATER_TEMP_STEP

        attributes = state.attributes or {}
        step = self._coerce(attributes.get("step"), DEFAULT_WATER_TEMP_STEP)
        if step <= 0:
            step = DEFAULT_WATER_TEMP_STEP
        minimum = self._coerce(attributes.get("min"), SUPPLY_TEMP_MIN)
        maximum = self._coerce(attributes.get("max"), SUPPLY_TEMP_MAX)
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        return minimum, maximum, step

    @staticmethod
    def _coerce(value: Any, default: float) -> float:
        """Coerce an attribute to float, falling back to a default."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    async def _async_call_set_value(self, entity_id: str, value: float, now: datetime) -> bool:
        """Call ``set_value`` on the target entity, handling all error types.

        Mirrors :class:`HeaterServiceCaller` error handling; failures are logged
        (rate-limited) and simply retried on the next cycle.
        """
        domain = HeaterServiceCaller.get_number_entity_domain(entity_id)
        try:
            await self.hass.services.async_call(
                domain,
                "set_value",
                {"entity_id": entity_id, "value": value},
                blocking=False,
            )
            self._last_write_error.pop(entity_id, None)
            _LOGGER.debug("Water temp control: wrote %.1f°C to %s", value, entity_id)
            return True
        except ServiceNotFound as err:
            self._log_write_error(entity_id, now, "service '%s.set_value' not found: %s", domain, err)
            return False
        except HomeAssistantError as err:
            self._log_write_error(entity_id, now, "Home Assistant error: %s", err)
            return False
        except Exception as err:  # noqa: BLE001 - one bad entity must not kill the cycle
            self._log_write_error(entity_id, now, "unexpected error: %s", err)
            return False

    def _log_write_error(self, entity_id: str, now: datetime, message: str, *args: Any) -> None:
        """Log a write failure at most once per hour per entity."""
        last = self._last_write_error.get(entity_id)
        if last is not None and (now - last).total_seconds() < WATER_TEMP_WARN_INTERVAL_SECONDS:
            return
        self._last_write_error[entity_id] = now
        _LOGGER.error("Water temp control: failed to write %s — " + message, entity_id, *args)
```

Add `WATER_TEMP_WARN_INTERVAL_SECONDS` to the const import block.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_water_temp_controller.py -v`
Expected: PASS — all write-policy tests green, Task 6 tests still green

- [ ] **Step 5: Lint and typecheck**

Run: `ruff check custom_components/adaptive_climate/managers/water_temp_controller.py tests/test_water_temp_controller.py && pyright custom_components/adaptive_climate/managers/water_temp_controller.py`
Expected: no findings

- [ ] **Step 6: Commit**

```bash
git add custom_components/adaptive_climate/managers/water_temp_controller.py tests/test_water_temp_controller.py
git commit -m "feat(watertemp): add safe-direction write policy with asymmetric dwell"
```

---

### Task 8: Interlocks, learning gate, timers and diagnostics

**Files:**
- Modify: `custom_components/adaptive_climate/managers/water_temp_controller.py`
- Test: `tests/test_water_temp_controller.py` (append)

**Interfaces:**
- Consumes: everything from Tasks 6-7.
- Produces:
  - `controller.async_start() -> None` (sync method that registers listeners), `controller.async_cleanup() -> None` (sync teardown; named for symmetry with `coordinator.async_cleanup`, called without await from the coordinator's async cleanup).
  - `controller.learning_gate(mode: str | None) -> bool` — accepts `"heat"`/`"cool"` HVAC states **and** the internal `"heating"`/`"cooling"` keys.
  - `controller.diagnostics() -> dict[str, Any]` with keys `mode`, `effective`, `dew_point`, `binding_constraint`, `ramp_active`, `days_remaining`, `worst_source`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_water_temp_controller.py`:

```python
# =============================================================================
# Interlocks
# =============================================================================


def binary_state(value):
    state = MagicMock()
    state.state = value
    state.attributes = {}
    return state


class TestInterlocks:
    @pytest.mark.asyncio
    async def test_condensation_sensor_on_parks_immediately(self):
        """A strapped-on pipe sensor is a measurement; dew point is an inference."""
        states = {COOL_ENTITY: number_state(19.0), "binary_sensor.condensation": binary_state("on")}
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {"climate_entity_id": "climate.living"}}},
            states=states,
            condensation_sensor="binary_sensor.condensation",
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert written_values(controller) == [22.0]

    @pytest.mark.asyncio
    async def test_interlock_park_bypasses_the_dwell_window(self):
        states = {COOL_ENTITY: number_state(19.0), "binary_sensor.condensation": binary_state("off")}
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {"climate_entity_id": "climate.living"}}},
            states=states,
            condensation_sensor="binary_sensor.condensation",
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)
        await controller.async_apply(NOW)  # writes 19.0

        states["binary_sensor.condensation"] = binary_state("on")
        await controller.async_apply(NOW + timedelta(minutes=1))

        assert written_values(controller) == [19.0, 22.0]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("override_type", ["open_window", "contact_open"])
    async def test_cool_zone_window_override_forces_a_park(self, override_type):
        """Humid night air onto a cold slab is the top condensation event."""
        states = {
            COOL_ENTITY: number_state(19.0),
            "climate.living": climate_state("cool", [{"type": override_type}]),
        }
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {"climate_entity_id": "climate.living"}}},
            states=states,
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert written_values(controller) == [22.0]
        assert controller.diagnostics()["binding_constraint"] == "interlock"

    @pytest.mark.asyncio
    async def test_normal_computation_resumes_thirty_minutes_after_clear(self):
        states = {COOL_ENTITY: number_state(22.0), "binary_sensor.condensation": binary_state("on")}
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {"climate_entity_id": "climate.living"}}},
            states=states,
            condensation_sensor="binary_sensor.condensation",
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)
        await controller.async_apply(NOW)

        states["binary_sensor.condensation"] = binary_state("off")
        await controller.async_apply(NOW + timedelta(minutes=10))
        assert written_values(controller) == [22.0]  # still holding

        await controller.async_apply(NOW + timedelta(minutes=45))
        assert written_values(controller) == [22.0, 19.0]

    @pytest.mark.asyncio
    async def test_heating_is_unaffected_by_cooling_interlocks(self):
        states = {
            HEAT_ENTITY: number_state(30.0),
            COOL_ENTITY: number_state(22.0),
            "binary_sensor.condensation": binary_state("on"),
        }
        controller = build_controller(
            cooling=cooling_config(),
            heating=heating_config(),
            zones_in_mode={"cool": {}, "heat": {"living": {}}},
            states=states,
            condensation_sensor="binary_sensor.condensation",
        )
        stub_scan(controller, dew_point=17.0)
        controller._ramp[WATER_TEMP_MODE_HEATING].last_active = NOW - timedelta(hours=1)

        await controller.async_apply(NOW)

        assert 35.0 in written_values(controller)


# =============================================================================
# Learning gate
# =============================================================================


class TestLearningGate:
    def test_gate_is_open_while_a_ramp_is_active(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0)
        controller.compute_targets(NOW)

        assert controller.learning_gate("cool") is True
        assert controller.learning_gate(WATER_TEMP_MODE_COOLING) is True
        assert controller.learning_gate("heat") is False

    @pytest.mark.asyncio
    async def test_gate_opens_for_one_settling_window_after_a_large_write(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(21.0)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        stub_scan(controller, dew_point=17.0)
        await controller.async_apply(NOW)  # 19.0, first write, no baseline
        stub_scan(controller, dew_point=19.5)
        await controller.async_apply(NOW + timedelta(minutes=5))  # 21.5, +2.5 degC

        controller._utcnow = lambda: NOW + timedelta(minutes=30)
        assert controller.learning_gate("cool") is True

        controller._utcnow = lambda: NOW + timedelta(minutes=120)
        assert controller.learning_gate("cool") is False

    @pytest.mark.asyncio
    async def test_small_writes_do_not_open_the_gate(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(19.0)},
        )
        controller._ramp[WATER_TEMP_MODE_COOLING].last_active = NOW - timedelta(hours=1)

        stub_scan(controller, dew_point=17.0)
        await controller.async_apply(NOW)  # 19.0
        stub_scan(controller, dew_point=17.4)
        await controller.async_apply(NOW + timedelta(minutes=5))  # 19.5, +0.5 degC

        controller._utcnow = lambda: NOW + timedelta(minutes=10)
        assert controller.learning_gate("cool") is False

    def test_gate_is_closed_for_unconfigured_modes_and_none(self):
        controller = build_controller(cooling=cooling_config())

        assert controller.learning_gate("heat") is False
        assert controller.learning_gate(None) is False
        assert controller.learning_gate("off") is False


# =============================================================================
# Diagnostics
# =============================================================================


class TestDiagnostics:
    def test_reports_the_active_cooling_state(self):
        controller = build_controller(
            cooling=cooling_config(),
            zones_in_mode={"cool": {"living": {}}},
            states={COOL_ENTITY: number_state(22.0)},
        )
        stub_scan(controller, dew_point=14.0, worst_source="kitchen")
        controller.compute_targets(NOW)

        diagnostics = controller.diagnostics()

        assert diagnostics["mode"] == WATER_TEMP_MODE_COOLING
        assert diagnostics["effective"] == pytest.approx(22.0)
        assert diagnostics["dew_point"] == pytest.approx(14.0)
        assert diagnostics["binding_constraint"] == WATER_TEMP_BINDING_RAMP
        assert diagnostics["ramp_active"] is True
        assert diagnostics["days_remaining"] == pytest.approx(6.0)
        assert diagnostics["worst_source"] == "kitchen"

    def test_reports_nothing_when_no_mode_is_active(self):
        controller = build_controller(cooling=cooling_config(), zones_in_mode={"cool": {}})
        stub_scan(controller, dew_point=14.0)
        controller.compute_targets(NOW)

        diagnostics = controller.diagnostics()

        assert diagnostics["mode"] is None
        assert diagnostics["effective"] is None
        assert diagnostics["ramp_active"] is False


# =============================================================================
# Timers
# =============================================================================


class TestTimers:
    def test_start_registers_a_started_listener_and_an_interval(self, monkeypatch):
        controller = build_controller(cooling=cooling_config())
        tracked = {}

        def fake_interval(_hass, action, interval):
            tracked["action"] = action
            tracked["interval"] = interval
            return lambda: tracked.update(interval_cancelled=True)

        monkeypatch.setattr(
            "custom_components.adaptive_climate.managers.water_temp_controller.async_track_time_interval",
            fake_interval,
        )
        controller.hass.bus.async_listen_once = MagicMock(return_value=lambda: tracked.update(once_cancelled=True))

        controller.async_start()

        assert tracked["interval"] == timedelta(seconds=300)
        controller.hass.bus.async_listen_once.assert_called_once()

    def test_cleanup_cancels_every_registered_handle(self, monkeypatch):
        controller = build_controller(cooling=cooling_config())
        cancelled = []

        monkeypatch.setattr(
            "custom_components.adaptive_climate.managers.water_temp_controller.async_track_time_interval",
            lambda _hass, _action, _interval: lambda: cancelled.append("interval"),
        )
        controller.hass.bus.async_listen_once = MagicMock(return_value=lambda: cancelled.append("once"))

        controller.async_start()
        controller.async_cleanup()

        assert sorted(cancelled) == ["interval", "once"]

    @pytest.mark.asyncio
    async def test_a_failing_cycle_does_not_kill_the_timer(self):
        controller = build_controller(cooling=cooling_config())
        controller.async_apply = AsyncMock(side_effect=RuntimeError("boom"))

        await controller._async_timer_tick(None)  # must not raise

        controller.async_apply.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_water_temp_controller.py::TestInterlocks -v`
Expected: FAIL — `TypeError: WaterTempController.__init__() got an unexpected keyword argument 'condensation_sensor'` / missing `learning_gate`

- [ ] **Step 3: Write minimal implementation**

Add to the imports in `water_temp_controller.py`:

```python
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CALLBACK_TYPE
from homeassistant.helpers.event import async_call_later, async_track_time_interval
```

and to the const import block:

```python
    WATER_TEMP_BINDING_INTERLOCK,
    WATER_TEMP_INTERLOCK_STABILIZATION_SECONDS,
    WATER_TEMP_STARTUP_DELAY_SECONDS,
    WATER_TEMP_UPDATE_INTERVAL_SECONDS,
```

Add to `__init__`:

```python
        self._interlock_engaged = False
        self._interlock_cleared_at: datetime | None = None
        self._started_unsub: CALLBACK_TYPE | None = None
        self._startup_unsub: CALLBACK_TYPE | None = None
        self._interval_unsub: CALLBACK_TYPE | None = None
```

Append these methods to the class:

```python
    # ── timers ───────────────────────────────────────────────────────────────

    def async_start(self) -> None:
        """Register the startup compute and the 5-minute recompute interval.

        Synchronous by design so it can be called from ``coordinator.__init__``.
        """
        self._started_unsub = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, self._async_on_ha_started
        )
        self._interval_unsub = async_track_time_interval(
            self.hass,
            self._async_timer_tick,
            timedelta(seconds=WATER_TEMP_UPDATE_INTERVAL_SECONDS),
        )
        _LOGGER.debug("Water temp control: timers registered")

    def async_cleanup(self) -> None:
        """Cancel every registered listener.  Called from coordinator cleanup."""
        for name in ("_started_unsub", "_startup_unsub", "_interval_unsub"):
            unsub = getattr(self, name)
            if unsub is not None:
                unsub()
                setattr(self, name, None)
        _LOGGER.debug("Water temp control: timers cancelled")

    async def _async_on_ha_started(self, _event: Any) -> None:
        """Schedule the first computation after a short startup delay."""
        self._started_unsub = None
        self._startup_unsub = async_call_later(
            self.hass, WATER_TEMP_STARTUP_DELAY_SECONDS, self._async_startup_compute
        )

    async def _async_startup_compute(self, _now: Any) -> None:
        """Run the first computation once zones have registered and state restored."""
        self._startup_unsub = None
        await self._async_timer_tick(None)

    async def _async_timer_tick(self, _now: Any) -> None:
        """Timer body — one bad cycle must never kill the interval."""
        try:
            await self.async_apply(self._utcnow())
        except Exception:  # noqa: BLE001 - keep the timer alive
            _LOGGER.exception("Water temp control: computation cycle failed")

    # ── interlocks ───────────────────────────────────────────────────────────

    def _cooling_interlocked(self, now: datetime) -> bool:
        """Return True while cooling must hold at its park value.

        True while the condensation sensor is ON or any COOL zone reports an
        ``open_window`` / ``contact_open`` override, and for 30 minutes after
        the last such condition clears.
        """
        active = self._interlock_condition_active()

        if active:
            self._interlock_engaged = True
            self._interlock_cleared_at = None
            return True

        if not self._interlock_engaged:
            return False

        if self._interlock_cleared_at is None:
            self._interlock_cleared_at = now
        elapsed = (now - self._interlock_cleared_at).total_seconds()
        if elapsed < WATER_TEMP_INTERLOCK_STABILIZATION_SECONDS:
            return True

        self._interlock_engaged = False
        self._interlock_cleared_at = None
        _LOGGER.info("Water temp control: cooling interlock cleared, resuming normal computation")
        return False

    def _interlock_condition_active(self) -> bool:
        """Return True while a raw interlock condition is present."""
        if self._condensation_sensor:
            state = self.hass.states.get(self._condensation_sensor)
            if state is not None and state.state == "on":
                return True

        for zone_data in self._coordinator.get_zones_in_mode(MODE_HVAC_STATE[WATER_TEMP_MODE_COOLING]).values():
            climate_entity_id = zone_data.get("climate_entity_id")
            if not climate_entity_id:
                continue
            state = self.hass.states.get(climate_entity_id)
            if state is None:
                continue
            status = state.attributes.get("status") or {}
            for override in status.get("overrides", []) or []:
                if override.get("type") in ("open_window", "contact_open"):
                    return True

        return False

    # ── learning gate ────────────────────────────────────────────────────────

    def learning_gate(self, mode: str | None) -> bool:
        """Return True while learning must be suppressed for the given mode.

        Water-temperature changes move the plant gain under the adaptive
        learner (zone gain ~ T_room - T_water); a multi-day ramp looks exactly
        like the UndershootDetector failure signature.

        Args:
            mode: HVAC state ("heat"/"cool") or internal key ("heating"/"cooling").

        Returns:
            True while a ramp is active for that mode, or within one settling
            window of a write that moved the value by >= 1.0 °C.
        """
        key = self._normalize_mode(mode)
        if key is None or key not in self.enabled_modes:
            return False

        if self._ramp[key].ramp_started is not None:
            return True

        until = self._gate_until.get(key)
        return until is not None and self._utcnow() < until

    @staticmethod
    def _normalize_mode(mode: str | None) -> str | None:
        """Map an HVAC state or internal key to an internal mode key."""
        if mode in (WATER_TEMP_MODE_COOLING, WATER_TEMP_MODE_HEATING):
            return mode
        if mode == "cool":
            return WATER_TEMP_MODE_COOLING
        if mode == "heat":
            return WATER_TEMP_MODE_HEATING
        return None

    # ── diagnostics ──────────────────────────────────────────────────────────

    def diagnostics(self) -> dict[str, Any]:
        """Return the diagnostic sensor payload."""
        mode: str | None = None
        for candidate in (WATER_TEMP_MODE_COOLING, WATER_TEMP_MODE_HEATING):
            if candidate in self._effective:
                mode = candidate
                break

        if mode is None:
            return {
                "mode": None,
                "effective": None,
                "dew_point": self._last_scan.dew_point if self._last_scan else None,
                "binding_constraint": None,
                "ramp_active": False,
                "days_remaining": None,
                "worst_source": self._last_scan.worst_source if self._last_scan else None,
            }

        ramp = self._ramp[mode]
        return {
            "mode": mode,
            "effective": self._effective.get(mode),
            "dew_point": self._last_scan.dew_point if self._last_scan else None,
            "binding_constraint": self._binding.get(mode),
            "ramp_active": ramp.ramp_started is not None,
            "days_remaining": self._days_remaining(mode),
            "worst_source": self._last_scan.worst_source if self._last_scan else None,
        }

    def _days_remaining(self, mode: str) -> float | None:
        """Return days left on an active ramp, or None."""
        ramp = self._ramp[mode]
        if ramp.ramp_started is None:
            return None
        current = self._effective.get(mode)
        if current is None:
            return None

        config = self._heating if mode == WATER_TEMP_MODE_HEATING else self._cooling
        default_rate = (
            DEFAULT_WATER_TEMP_HEATING_RAMP_RATE
            if mode == WATER_TEMP_MODE_HEATING
            else DEFAULT_WATER_TEMP_COOLING_RAMP_RATE
        )
        rate = float((config or {}).get(CONF_WATER_TEMP_RAMP_RATE, default_rate))
        if rate <= 0:
            return None

        if mode == WATER_TEMP_MODE_HEATING:
            if self._heating_target is None:
                return None
            remaining = self._heating_target - current
        else:
            floor = float(
                (config or {}).get(CONF_WATER_TEMP_MIN_SUPPLY_TEMP, DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP)
            )
            dew_target = floor
            if self._last_scan is not None and self._last_scan.dew_point is not None and not self._last_scan.blind:
                margin = float(
                    (config or {}).get(CONF_WATER_TEMP_DEW_POINT_MARGIN, DEFAULT_WATER_TEMP_DEW_POINT_MARGIN)
                )
                dew_target = max(self._last_scan.dew_point + margin, floor)
            remaining = current - dew_target

        return round(max(0.0, remaining) / rate, 2)
```

Wire the interlock into `_compute_cooling` — insert immediately after the `if not self._mode_is_active(...)` guard:

```python
        if self._cooling_interlocked(now):
            self._binding[WATER_TEMP_MODE_COOLING] = WATER_TEMP_BINDING_INTERLOCK
            return self._park_value(WATER_TEMP_MODE_COOLING)
```

and make `async_apply` force the write when cooling is interlocked — replace the `if value is not None:` branch body with:

```python
            value = targets.get(mode)
            if value is not None:
                self._was_active[mode] = True
                interlocked = (
                    mode == WATER_TEMP_MODE_COOLING
                    and self._binding.get(mode) == WATER_TEMP_BINDING_INTERLOCK
                )
                await self._async_write(mode, entity_id, value, now=now, force=interlocked)
                continue
```

Finally, accept `condensation_sensor` from the test helper's top-level config — no code change is needed, `CONF_WATER_TEMP_CONDENSATION_SENSOR == "condensation_sensor"` is already read in `__init__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_water_temp_controller.py -v`
Expected: PASS — interlock, gate, diagnostics and timer tests green; Tasks 6-7 tests still green

- [ ] **Step 5: Verify the file is under the size ceiling**

Run: `wc -l custom_components/adaptive_climate/managers/water_temp_controller.py`
Expected: under 800 lines. If it is over, extract the write policy into `managers/water_temp_writer.py` and report the split before continuing.

- [ ] **Step 6: Lint and typecheck**

Run: `ruff check custom_components/adaptive_climate/managers/water_temp_controller.py tests/test_water_temp_controller.py && pyright custom_components/adaptive_climate/managers/water_temp_controller.py`
Expected: no findings

- [ ] **Step 7: Commit**

```bash
git add custom_components/adaptive_climate/managers/water_temp_controller.py tests/test_water_temp_controller.py
git commit -m "feat(watertemp): add interlocks, learning gate, timers and diagnostics"
```

---

### Task 9: Persistence of water temperature state

**Files:**
- Modify: `custom_components/adaptive_climate/adaptive/persistence.py:337` (append after `async_save_manifold_state`)
- Test: `tests/test_water_temp_persistence.py`

**Interfaces:**
- Consumes: `LearningDataStore._data`, `LearningDataStore._store`, `LearningDataStore._save_lock`.
- Produces:
  - `async LearningDataStore.async_load_water_temp_state() -> dict[str, Any] | None`
  - `async LearningDataStore.async_save_water_temp_state(state: dict[str, Any]) -> None`
  - Store key: top-level `"water_temp_state"`. **`STORAGE_VERSION` stays at 5.**

- [ ] **Step 1: Write the failing test**

Create `tests/test_water_temp_persistence.py`:

```python
"""Tests for water temperature state persistence in LearningDataStore."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.adaptive_climate.adaptive.persistence import (
    STORAGE_VERSION,
    LearningDataStore,
)

SAMPLE_STATE = {
    "cooling": {
        "last_active": "2026-08-01T12:00:00+00:00",
        "ramp_started": "2026-07-28T09:00:00+00:00",
        "ramp_start_value": 22.0,
    },
    "heating": {"last_active": None, "ramp_started": None, "ramp_start_value": None},
    "last_written": {"number.hp_cool_supply": 19.5},
}


@pytest.fixture
def store():
    instance = LearningDataStore(MagicMock())
    instance._store = MagicMock()
    instance._store.async_save = AsyncMock(return_value=None)
    return instance


@pytest.mark.asyncio
async def test_save_then_load_round_trips(store):
    await store.async_save_water_temp_state(SAMPLE_STATE)

    assert await store.async_load_water_temp_state() == SAMPLE_STATE


@pytest.mark.asyncio
async def test_load_returns_none_when_absent(store):
    assert await store.async_load_water_temp_state() is None


@pytest.mark.asyncio
async def test_save_writes_through_to_the_ha_store(store):
    await store.async_save_water_temp_state(SAMPLE_STATE)

    store._store.async_save.assert_awaited_once()
    saved = store._store.async_save.await_args.args[0]
    assert saved["water_temp_state"] == SAMPLE_STATE


@pytest.mark.asyncio
async def test_save_preserves_existing_top_level_keys(store):
    store._data["manifold_state"] = {"ground_floor": "2026-07-01T00:00:00+00:00"}
    store._data["zones"] = {"living": {"adaptive_learner": {}}}

    await store.async_save_water_temp_state(SAMPLE_STATE)

    assert store._data["manifold_state"] == {"ground_floor": "2026-07-01T00:00:00+00:00"}
    assert store._data["zones"] == {"living": {"adaptive_learner": {}}}
    assert store._data["version"] == STORAGE_VERSION


@pytest.mark.asyncio
async def test_water_temp_state_is_additive_and_does_not_bump_the_version(store):
    """_validate_data only requires version + zones — an extra key is additive."""
    await store.async_save_water_temp_state(SAMPLE_STATE)

    assert STORAGE_VERSION == 5
    assert store._validate_data(store._data) is True


@pytest.mark.asyncio
async def test_load_requires_an_initialized_store():
    instance = LearningDataStore(MagicMock())

    with pytest.raises(RuntimeError, match="Store not initialized"):
        await instance.async_load_water_temp_state()


@pytest.mark.asyncio
async def test_save_requires_an_initialized_store():
    instance = LearningDataStore(MagicMock())

    with pytest.raises(RuntimeError, match="Store not initialized"):
        await instance.async_save_water_temp_state(SAMPLE_STATE)


@pytest.mark.asyncio
async def test_load_requires_a_hass_instance(store):
    store.hass = None

    with pytest.raises(RuntimeError, match="requires HomeAssistant instance"):
        await store.async_load_water_temp_state()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_water_temp_persistence.py -v`
Expected: FAIL — `AttributeError: 'LearningDataStore' object has no attribute 'async_save_water_temp_state'`

- [ ] **Step 3: Write minimal implementation**

Append to `custom_components/adaptive_climate/adaptive/persistence.py` (after `async_save_manifold_state`, at the end of the class):

```python
    async def async_load_water_temp_state(self) -> dict[str, Any] | None:
        """
        Load water temperature control state from HA Store.

        Returns:
            Dict with per-mode ramp state and last-written values, or None if
            no state has been persisted yet.
        """
        if self.hass is None:
            raise RuntimeError("async_load_water_temp_state requires HomeAssistant instance")

        if self._store is None:
            raise RuntimeError("Store not initialized - call async_load() first")

        # Water temp state is stored at top level, mirroring manifold_state.
        # This is additive: _validate_data only requires version + zones, so no
        # STORAGE_VERSION bump is needed.
        water_temp_state = self._data.get("water_temp_state")
        if water_temp_state is None:
            _LOGGER.debug("No water temperature state found in storage")
            return None

        _LOGGER.info("Loaded water temperature control state")
        return water_temp_state

    async def async_save_water_temp_state(self, state: dict[str, Any]) -> None:
        """
        Save water temperature control state to HA Store.

        Args:
            state: Dict with per-mode ramp state (ISO timestamps) and the last
                value written to each target entity.
        """
        if self.hass is None:
            raise RuntimeError("async_save_water_temp_state requires HomeAssistant instance")

        if self._store is None:
            raise RuntimeError("Store not initialized - call async_load() first")

        if self._save_lock is None:
            self._save_lock = asyncio.Lock()

        async with self._save_lock:
            self._data["water_temp_state"] = state
            await self._store.async_save(self._data)
            _LOGGER.debug("Saved water temperature control state")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_water_temp_persistence.py tests/test_integration_persistence.py -v`
Expected: PASS — new file green, existing persistence tests unaffected

- [ ] **Step 5: Lint and typecheck**

Run: `ruff check custom_components/adaptive_climate/adaptive/persistence.py tests/test_water_temp_persistence.py && pyright custom_components/adaptive_climate/adaptive/persistence.py`
Expected: no findings

- [ ] **Step 6: Commit**

```bash
git add custom_components/adaptive_climate/adaptive/persistence.py tests/test_water_temp_persistence.py
git commit -m "feat(persistence): store water temperature control state"
```

---

### Task 10: Wire the controller into the coordinator and integration lifecycle

**Files:**
- Modify: `custom_components/adaptive_climate/coordinator.py:69-90` (construction), `:803-814` (cleanup), plus new properties
- Modify: `custom_components/adaptive_climate/climate_setup.py:241-249` (restore)
- Modify: `custom_components/adaptive_climate/__init__.py:748-763` (shutdown save), `:827-836` (unload save)
- Test: `tests/test_water_temp_wiring.py`

**Interfaces:**
- Consumes: `WaterTempController` (Tasks 6-8), `async_load/save_water_temp_state` (Task 9), `get_zones_in_mode` (Task 4).
- Produces:
  - `coordinator.water_temp_controller -> WaterTempController | None`
  - `coordinator.water_temp_learning_gate(mode: str | None) -> bool`
  - `hass.data[DOMAIN]["coordinator"].water_temp_controller` is the single instance; teardown lives in `coordinator.async_cleanup()`. Do **not** use `hass.data[DOMAIN]["unsub_callbacks"]`, which is created later in setup.

- [ ] **Step 1: Write the failing test**

Create `tests/test_water_temp_wiring.py`:

```python
"""Tests for water temperature controller wiring into coordinator + lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.adaptive_climate.const import (
    CONF_WATER_TEMP_CONTROL,
    CONF_WATER_TEMP_COOLING,
    CONF_WATER_TEMP_TARGET_ENTITY,
)
from custom_components.adaptive_climate.coordinator import AdaptiveThermostatCoordinator


def make_coordinator(config):
    """Build a coordinator without running DataUpdateCoordinator.__init__."""
    coordinator = AdaptiveThermostatCoordinator.__new__(AdaptiveThermostatCoordinator)
    coordinator.hass = MagicMock()
    coordinator._zones = {}
    coordinator._demand_states = {}
    coordinator._config = config
    coordinator._startup_eval_unsub = None
    coordinator._outdoor_temp_unsub = None
    coordinator._water_temp_controller = None
    return coordinator


COOLING_CONFIG = {
    CONF_WATER_TEMP_CONTROL: {
        CONF_WATER_TEMP_COOLING: {CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_cool"}
    }
}


class TestCoordinatorWiring:
    def test_controller_is_built_from_the_passed_domain_config(self):
        """supply_temperature lands in hass.data only AFTER the coordinator exists."""
        with patch(
            "custom_components.adaptive_climate.coordinator.WaterTempController"
        ) as controller_cls:
            coordinator = make_coordinator({**COOLING_CONFIG, "supply_temperature": 38.0})
            coordinator._setup_water_temp_control()

        controller_cls.assert_called_once()
        kwargs = controller_cls.call_args.kwargs
        assert kwargs["supply_temperature"] == 38.0
        controller_cls.return_value.async_start.assert_called_once()

    def test_no_controller_when_water_temp_control_is_absent(self):
        coordinator = make_coordinator({})
        coordinator._setup_water_temp_control()

        assert coordinator.water_temp_controller is None

    def test_no_controller_when_neither_half_is_configured(self):
        coordinator = make_coordinator({CONF_WATER_TEMP_CONTROL: {"idle_days": 7}})
        coordinator._setup_water_temp_control()

        assert coordinator.water_temp_controller is None

    @pytest.mark.asyncio
    async def test_cleanup_tears_the_controller_down(self):
        coordinator = make_coordinator(COOLING_CONFIG)
        controller = MagicMock()
        coordinator._water_temp_controller = controller

        await coordinator.async_cleanup()

        controller.async_cleanup.assert_called_once()
        assert coordinator.water_temp_controller is None

    @pytest.mark.asyncio
    async def test_cleanup_is_safe_without_a_controller(self):
        coordinator = make_coordinator({})

        await coordinator.async_cleanup()  # must not raise

        assert coordinator.water_temp_controller is None

    def test_learning_gate_delegates_to_the_controller(self):
        coordinator = make_coordinator(COOLING_CONFIG)
        controller = MagicMock()
        controller.learning_gate = MagicMock(return_value=True)
        coordinator._water_temp_controller = controller

        assert coordinator.water_temp_learning_gate("cool") is True
        controller.learning_gate.assert_called_once_with("cool")

    def test_learning_gate_is_false_without_a_controller_or_mode(self):
        coordinator = make_coordinator({})

        assert coordinator.water_temp_learning_gate("cool") is False
        assert coordinator.water_temp_learning_gate(None) is False


class TestRestoreAndSave:
    @pytest.mark.asyncio
    async def test_restore_applies_persisted_state_and_marks_restored(self):
        from custom_components.adaptive_climate.climate_setup import (
            async_restore_water_temp_state,
        )

        controller = MagicMock()
        store = MagicMock()
        store.async_load_water_temp_state = AsyncMock(return_value={"cooling": {}})

        await async_restore_water_temp_state(store, controller)

        controller.restore_state.assert_called_once_with({"cooling": {}})

    @pytest.mark.asyncio
    async def test_restore_still_marks_restored_when_nothing_is_persisted(self):
        from custom_components.adaptive_climate.climate_setup import (
            async_restore_water_temp_state,
        )

        controller = MagicMock()
        store = MagicMock()
        store.async_load_water_temp_state = AsyncMock(return_value=None)

        await async_restore_water_temp_state(store, controller)

        controller.restore_state.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_restore_is_a_noop_without_a_controller(self):
        from custom_components.adaptive_climate.climate_setup import (
            async_restore_water_temp_state,
        )

        store = MagicMock()
        store.async_load_water_temp_state = AsyncMock(return_value={"cooling": {}})

        await async_restore_water_temp_state(store, None)

        store.async_load_water_temp_state.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_save_helper_persists_the_controller_snapshot(self):
        from custom_components.adaptive_climate import async_save_water_temp_state_now

        hass = MagicMock()
        controller = MagicMock()
        controller.get_state_for_persistence = MagicMock(return_value={"cooling": {}})
        coordinator = MagicMock()
        coordinator.water_temp_controller = controller
        store = MagicMock()
        store.async_save_water_temp_state = AsyncMock(return_value=None)
        hass.data = {
            "adaptive_climate": {"coordinator": coordinator, "learning_store": store}
        }

        await async_save_water_temp_state_now(hass)

        store.async_save_water_temp_state.assert_awaited_once_with({"cooling": {}})

    @pytest.mark.asyncio
    async def test_save_helper_is_a_noop_without_a_controller_or_store(self):
        from custom_components.adaptive_climate import async_save_water_temp_state_now

        hass = MagicMock()
        hass.data = {"adaptive_climate": {}}

        await async_save_water_temp_state_now(hass)  # must not raise

    @pytest.mark.asyncio
    async def test_save_helper_swallows_store_errors(self):
        from custom_components.adaptive_climate import async_save_water_temp_state_now

        hass = MagicMock()
        controller = MagicMock()
        controller.get_state_for_persistence = MagicMock(return_value={})
        coordinator = MagicMock()
        coordinator.water_temp_controller = controller
        store = MagicMock()
        store.async_save_water_temp_state = AsyncMock(side_effect=OSError("disk full"))
        hass.data = {
            "adaptive_climate": {"coordinator": coordinator, "learning_store": store}
        }

        await async_save_water_temp_state_now(hass)  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_water_temp_wiring.py -v`
Expected: FAIL — `AttributeError: ... has no attribute '_setup_water_temp_control'`

- [ ] **Step 3: Wire the coordinator**

In `custom_components/adaptive_climate/coordinator.py`, add to the relative-import try block (and the absolute fallback):

```python
    from .managers.water_temp_controller import WaterTempController
```
```python
    from managers.water_temp_controller import WaterTempController  # type: ignore[no-redef]
```

Add to the const import in the same block: `from .const import DOMAIN, CONF_SUPPLY_TEMPERATURE, CONF_WATER_TEMP_CONTROL, CONF_WATER_TEMP_COOLING, CONF_WATER_TEMP_HEATING` (mirror in the fallback).

In `__init__`, insert after the auto-mode-switching block (line 74) and before `self._setup_outdoor_temp_listener()`:

```python
        # Water temperature control (if configured)
        self._water_temp_controller: WaterTempController | None = None
        self._setup_water_temp_control()
```

Add these methods next to the other properties (e.g. after `min_cooling_target`):

```python
    def _setup_water_temp_control(self) -> None:
        """Construct the water temperature controller when configured.

        Reads from ``self._config`` (the domain config passed to __init__) rather
        than ``hass.data[DOMAIN]`` because ``supply_temperature`` is written to
        hass.data only *after* the coordinator has been constructed.
        """
        water_temp_config = self._config.get(CONF_WATER_TEMP_CONTROL)
        if not water_temp_config:
            return
        if not water_temp_config.get(CONF_WATER_TEMP_COOLING) and not water_temp_config.get(
            CONF_WATER_TEMP_HEATING
        ):
            return

        self._water_temp_controller = WaterTempController(
            self.hass,
            self,
            water_temp_config,
            supply_temperature=self._config.get(CONF_SUPPLY_TEMPERATURE),
        )
        self._water_temp_controller.async_start()
        _LOGGER.info("Water temperature control enabled")

    @property
    def water_temp_controller(self) -> WaterTempController | None:
        """Return the water temperature controller, or None if not configured."""
        return self._water_temp_controller

    def water_temp_learning_gate(self, mode: str | None) -> bool:
        """Return True while water-temp changes should suppress zone learning.

        Args:
            mode: The zone's HVAC mode ("heat"/"cool"), or None.

        Returns:
            True when the controller reports an active ramp or a recent large
            write for that mode.
        """
        if self._water_temp_controller is None or mode is None:
            return False
        return self._water_temp_controller.learning_gate(mode)
```

Extend `async_cleanup` (line 803):

```python
        # Cancel water temperature control timers
        if self._water_temp_controller is not None:
            self._water_temp_controller.async_cleanup()
            self._water_temp_controller = None
            _LOGGER.debug("Cleaned up water temperature controller")
```

- [ ] **Step 4: Wire the restore in `climate_setup.py`**

Add this helper next to `build_dew_point_zone_data`:

```python
async def async_restore_water_temp_state(learning_store: Any, controller: Any) -> None:
    """Restore water temperature control state from the learning store.

    Mirrors the manifold restore: the coordinator (and therefore the controller)
    is created in ``async_setup`` before the store exists, so restoration happens
    here, on first-zone setup.  ``restore_state`` is always called — even with
    ``None`` — so the controller's ``_restored`` gate opens on first run too.

    Args:
        learning_store: The LearningDataStore singleton.
        controller: WaterTempController instance, or None when not configured.
    """
    if controller is None:
        return
    water_temp_state = await learning_store.async_load_water_temp_state()
    controller.restore_state(water_temp_state)
    _LOGGER.info("Restored water temperature control state")
```

Call it inside the first-zone branch, right after the manifold restore block (lines 244-249):

```python
        # Restore water temperature control state (same reason as manifold above)
        coordinator = hass.data[DOMAIN].get("coordinator")
        if coordinator is not None:
            await async_restore_water_temp_state(learning_store, coordinator.water_temp_controller)
```

- [ ] **Step 5: Wire the saves in `__init__.py`**

Add this helper next to `async_send_notification`:

```python
async def async_save_water_temp_state_now(hass: HomeAssistant) -> None:
    """Persist the water temperature controller's state immediately.

    Called on ``homeassistant_stop`` and on unload so a ramp survives a restart.
    Never raises — a failed save must not block shutdown.

    Args:
        hass: Home Assistant instance.
    """
    domain_data = hass.data.get(DOMAIN, {})
    coordinator = domain_data.get("coordinator")
    learning_store = domain_data.get("learning_store")
    controller = getattr(coordinator, "water_temp_controller", None) if coordinator else None

    if controller is None or learning_store is None:
        return

    try:
        await learning_store.async_save_water_temp_state(controller.get_state_for_persistence())
        _LOGGER.info("Saved water temperature control state")
    except Exception as err:  # noqa: BLE001 - shutdown must not fail on a bad save
        _LOGGER.error("Failed to save water temperature state: %s", err)
```

Call it from the shutdown handler at line 748 (rename the handler to reflect its wider scope):

```python
    # Register shutdown handler for manifold + water temperature state persistence
    async def _async_save_state_on_shutdown(event):
        """Save manifold and water temperature state on Home Assistant shutdown."""
        manifold_registry = hass.data.get(DOMAIN, {}).get("manifold_registry")
        learning_store = hass.data.get(DOMAIN, {}).get("learning_store")

        if manifold_registry and learning_store:
            try:
                manifold_state = manifold_registry.get_state_for_persistence()
                await learning_store.async_save_manifold_state(manifold_state)
                _LOGGER.info("Saved manifold state on shutdown: %d manifolds", len(manifold_state))
            except Exception as e:
                _LOGGER.error("Failed to save manifold state on shutdown: %s", e)

        await async_save_water_temp_state_now(hass)

    # Listen for HA stop event
    shutdown_unsub = hass.bus.async_listen_once("homeassistant_stop", _async_save_state_on_shutdown)
```

And in `async_unload`, immediately after the manifold save block (line 836):

```python
    # Save water temperature state on unload
    await async_save_water_temp_state_now(hass)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_water_temp_wiring.py tests/test_coordinator.py tests/test_climate_setup.py tests/test_init.py -v`
Expected: PASS — new wiring tests green, no regressions

- [ ] **Step 7: Lint and typecheck**

Run: `ruff check custom_components/adaptive_climate/coordinator.py custom_components/adaptive_climate/climate_setup.py custom_components/adaptive_climate/__init__.py tests/test_water_temp_wiring.py && pyright custom_components/adaptive_climate/coordinator.py custom_components/adaptive_climate/climate_setup.py custom_components/adaptive_climate/__init__.py`
Expected: no findings

- [ ] **Step 8: Commit**

```bash
git add custom_components/adaptive_climate/coordinator.py custom_components/adaptive_climate/climate_setup.py custom_components/adaptive_climate/__init__.py tests/test_water_temp_wiring.py
git commit -m "feat(watertemp): wire controller into coordinator lifecycle and persistence"
```

---

### Task 11: Learning protection — suppress cycle recording and undershoot detection

**Files:**
- Modify: `custom_components/adaptive_climate/climate.py:953-958`
- Modify: `custom_components/adaptive_climate/climate_control.py:157-164`
- Modify: `custom_components/adaptive_climate/managers/pause_detector.py:38-119`
- Modify: `custom_components/adaptive_climate/managers/state_attributes.py:762-775`
- Test: `tests/test_water_temp_learning_gate.py`

**Interfaces:**
- Consumes: `coordinator.water_temp_learning_gate(mode)` (Task 10).
- Produces:
  - `AdaptiveThermostat.water_temp_learning_gate_active -> bool`
  - `AdaptiveThermostat.in_learning_grace_period` now also True while the gate is active — this is what feeds `CycleMetricsRecorder`'s `get_in_grace_period` callback (`climate_init.py:358`), so cycle recording is suppressed for free.
  - `PauseDetector(..., water_temp_gate: bool = False)` and `PauseDetector.from_entity` reading `water_temp_learning_gate_active` — makes learning status report `idle`.
  - `state_attributes` emits the existing `learning_grace` override while the gate is active.

- [ ] **Step 1: Write the failing test**

Create `tests/test_water_temp_learning_gate.py`:

```python
"""Tests for water-temp learning suppression across the thermostat surface."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.adaptive_climate.managers.pause_detector import PauseDetector


class FakeEntity:
    """Minimal thermostat-like object for PauseDetector.from_entity."""

    def __init__(self, water_temp_gate=False):
        self._night_setback_controller = None
        self._contact_sensor_handler = None
        self._humidity_detector = None
        self.water_temp_learning_gate_active = water_temp_gate


class TestPauseDetectorGate:
    def test_learning_is_paused_while_the_gate_is_open(self):
        assert PauseDetector(water_temp_gate=True).is_learning_paused() is True

    def test_learning_is_not_paused_when_the_gate_is_closed(self):
        assert PauseDetector(water_temp_gate=False).is_learning_paused() is False

    def test_from_entity_picks_up_the_gate_flag(self):
        assert PauseDetector.from_entity(FakeEntity(True)).is_learning_paused() is True
        assert PauseDetector.from_entity(FakeEntity(False)).is_learning_paused() is False

    def test_from_entity_defaults_to_false_for_objects_without_the_property(self):
        assert PauseDetector.from_entity(object()).is_learning_paused() is False

    def test_control_is_not_paused_by_the_water_temp_gate(self):
        """The gate suppresses learning, not the actuator."""
        assert PauseDetector(water_temp_gate=True).is_control_paused("cool") is False


class TestThermostatGateProperty:
    @staticmethod
    def _thermostat(gate_value, hvac_mode="cool"):
        from custom_components.adaptive_climate.climate import AdaptiveThermostat

        thermostat = AdaptiveThermostat.__new__(AdaptiveThermostat)
        thermostat._hvac_mode = hvac_mode
        thermostat._night_setback_controller = None
        coordinator = MagicMock()
        coordinator.water_temp_learning_gate = MagicMock(return_value=gate_value)
        thermostat.hass = MagicMock()
        thermostat.hass.data = {"adaptive_climate": {"coordinator": coordinator}}
        return thermostat, coordinator

    def test_property_delegates_to_the_coordinator_with_the_current_mode(self):
        thermostat, coordinator = self._thermostat(True, hvac_mode="cool")

        assert thermostat.water_temp_learning_gate_active is True
        coordinator.water_temp_learning_gate.assert_called_once_with("cool")

    def test_property_is_false_without_a_coordinator(self):
        from custom_components.adaptive_climate.climate import AdaptiveThermostat

        thermostat = AdaptiveThermostat.__new__(AdaptiveThermostat)
        thermostat._hvac_mode = "cool"
        thermostat.hass = MagicMock()
        thermostat.hass.data = {}

        assert thermostat.water_temp_learning_gate_active is False

    def test_grace_period_is_true_while_the_gate_is_open(self):
        """This is the hook CycleMetricsRecorder reads to skip cycle recording."""
        thermostat, _ = self._thermostat(True)

        assert thermostat.in_learning_grace_period is True

    def test_grace_period_still_reflects_night_setback_when_the_gate_is_closed(self):
        thermostat, _ = self._thermostat(False)
        night_setback = MagicMock()
        night_setback.in_learning_grace_period = True
        thermostat._night_setback_controller = night_setback

        assert thermostat.in_learning_grace_period is True

    def test_grace_period_is_false_when_neither_source_is_active(self):
        thermostat, _ = self._thermostat(False)
        night_setback = MagicMock()
        night_setback.in_learning_grace_period = False
        thermostat._night_setback_controller = night_setback

        assert thermostat.in_learning_grace_period is False
```

Also append to `tests/test_water_temp_learning_gate.py` a check that the undershoot detector is skipped, driven directly off the guard helper:

```python
class TestUndershootSuppression:
    def test_undershoot_update_is_gated_on_the_water_temp_flag(self):
        """The guard in climate_control must include the gate flag."""
        import inspect

        from custom_components.adaptive_climate import climate_control

        source = inspect.getsource(climate_control)
        assert "not self.water_temp_learning_gate_active" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_water_temp_learning_gate.py -v`
Expected: FAIL — `TypeError: PauseDetector.__init__() got an unexpected keyword argument 'water_temp_gate'`

- [ ] **Step 3: Update `PauseDetector`**

In `custom_components/adaptive_climate/managers/pause_detector.py`, change `__init__`:

```python
    def __init__(
        self,
        night_setback_controller: NightSetbackManager | None = None,
        contact_sensor_handler: ContactSensorHandler | None = None,
        humidity_detector: HumidityDetector | None = None,
        water_temp_gate: bool = False,
    ) -> None:
        """Initialise with optional component references.

        Args:
            night_setback_controller: Checked for ``in_learning_grace_period``
                property when evaluating learning pauses.
            contact_sensor_handler: Checked for open contacts (learning) or
                delayed contact actions (control).
            humidity_detector: Checked via ``should_pause()`` for both flavours.
            water_temp_gate: True while the water-temperature controller is
                ramping or settling after a large write.  Suppresses learning
                only — the actuator keeps running.
        """
        self._night_setback_controller = night_setback_controller
        self._contact_sensor_handler = contact_sensor_handler
        self._humidity_detector = humidity_detector
        self._water_temp_gate = water_temp_gate
```

`from_entity`:

```python
        return cls(
            night_setback_controller=getattr(entity, "_night_setback_controller", None),
            contact_sensor_handler=getattr(entity, "_contact_sensor_handler", None),
            humidity_detector=getattr(entity, "_humidity_detector", None),
            water_temp_gate=bool(getattr(entity, "water_temp_learning_gate_active", False)),
        )
```

And add a fourth check at the end of `is_learning_paused`, before `return False`:

```python
        # 4. Water temperature ramp / post-write settling window
        if self._water_temp_gate:
            return True
```

Update the `is_learning_paused` docstring to list the fourth condition.

- [ ] **Step 4: Update `climate.py`**

Replace the `in_learning_grace_period` property at line 953 and add the new property above it:

```python
    @property
    def water_temp_learning_gate_active(self) -> bool:
        """Return True while water temperature changes suppress this zone's learning.

        Water-temp changes move the plant gain under the adaptive learner
        (zone gain ~ T_room - T_water); a multi-day ramp looks exactly like the
        UndershootDetector failure signature.
        """
        coordinator = self._coordinator
        if coordinator is None:
            return False
        try:
            return bool(coordinator.water_temp_learning_gate(self._hvac_mode))
        except (TypeError, AttributeError):
            return False

    @property
    def in_learning_grace_period(self) -> bool:
        """Check if learning should be paused.

        True after a recent night setback transition, or while the water
        temperature controller is ramping / settling after a large write.
        """
        if self.water_temp_learning_gate_active:
            return True
        if self._night_setback_controller:
            return self._night_setback_controller.in_learning_grace_period
        # No night setback controller and no water-temp gate means no grace period
        return False
```

- [ ] **Step 5: Update `climate_control.py`**

Change the undershoot guard at line 157:

```python
                # Update undershoot detector and check for Ki adjustment.
                # Skipped while the water temperature is ramping: a moving supply
                # temperature produces exactly the undershoot signature this
                # detector looks for, and the resulting Ki boosts take weeks to unwind.
                if (
                    self._hvac_mode == HVACMode.HEAT
                    and not self.water_temp_learning_gate_active
                    and coordinator
                    and self._zone_id
                    and self._current_temp is not None
                    and self._target_temp is not None
                ):
```

- [ ] **Step 6: Update `state_attributes.py`**

In the `# === Learning grace override data ===` block (line 762), insert before the `if thermostat._night_setback_controller:` line:

```python
    # The water-temperature ramp gate surfaces through the same learning_grace override
    try:
        if getattr(thermostat, "water_temp_learning_gate_active", False):
            learning_grace_active = True
    except (TypeError, AttributeError):
        pass

```

and change the night-setback branch so it does not clear the flag:

```python
    if thermostat._night_setback_controller:
        try:
            if thermostat._night_setback_controller.in_learning_grace_period:
                learning_grace_active = True
                grace_end = getattr(thermostat._night_setback_controller, "_learning_grace_end", None)
                if grace_end:
                    learning_grace_until = grace_end.isoformat()
        except (TypeError, AttributeError):
            pass
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_water_temp_learning_gate.py tests/managers -v && pytest tests/test_climate.py tests/test_climate_control.py tests/test_integration_overrides.py -v`
Expected: PASS — new tests green, no regressions in existing pause/override tests

- [ ] **Step 8: Lint and typecheck**

Run: `ruff check custom_components/adaptive_climate/climate.py custom_components/adaptive_climate/climate_control.py custom_components/adaptive_climate/managers/pause_detector.py custom_components/adaptive_climate/managers/state_attributes.py tests/test_water_temp_learning_gate.py && pyright custom_components/adaptive_climate/climate.py custom_components/adaptive_climate/climate_control.py custom_components/adaptive_climate/managers/pause_detector.py custom_components/adaptive_climate/managers/state_attributes.py`
Expected: no findings

- [ ] **Step 9: Commit**

```bash
git add custom_components/adaptive_climate/climate.py custom_components/adaptive_climate/climate_control.py custom_components/adaptive_climate/managers/pause_detector.py custom_components/adaptive_climate/managers/state_attributes.py tests/test_water_temp_learning_gate.py
git commit -m "feat(learning): suppress cycle recording and undershoot during water temp ramps"
```

---

### Task 12: Cooling clamp unification

**Files:**
- Modify: `custom_components/adaptive_climate/coordinator.py:337-343`
- Modify: `custom_components/adaptive_climate/climate.py:1006-1018`
- Modify: `custom_components/adaptive_climate/__init__.py` (setup warning, after coordinator creation at line 477)
- Test: `tests/test_water_temp_clamp.py`

**Interfaces:**
- Consumes: `controller.effective_cooling_supply_temp` (Task 6), `coordinator.water_temp_controller` (Task 10).
- Produces:
  - `coordinator.effective_cooling_supply_temp -> float | None` — the controller's live value, falling back to the static `cooling_supply_temp`.
  - `coordinator.min_cooling_target` now reads `effective_cooling_supply_temp`.
  - `check_cooling_supply_conflict(domain_config: dict) -> str | None` in `__init__.py` — the warning message, or None.

- [ ] **Step 1: Write the failing test**

Create `tests/test_water_temp_clamp.py`:

```python
"""Tests for unifying min_cooling_target with the dynamic water temperature."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.adaptive_climate.const import (
    CONF_COOLING_SUPPLY_MARGIN,
    CONF_COOLING_SUPPLY_TEMP,
    CONF_WATER_TEMP_CONTROL,
    CONF_WATER_TEMP_COOLING,
    CONF_WATER_TEMP_MIN_SUPPLY_TEMP,
    CONF_WATER_TEMP_TARGET_ENTITY,
)
from custom_components.adaptive_climate.coordinator import AdaptiveThermostatCoordinator


def make_coordinator(config, controller=None):
    coordinator = AdaptiveThermostatCoordinator.__new__(AdaptiveThermostatCoordinator)
    coordinator.hass = MagicMock()
    coordinator._zones = {}
    coordinator._config = config
    coordinator._water_temp_controller = controller
    return coordinator


def controller_with(effective):
    controller = MagicMock()
    controller.effective_cooling_supply_temp = effective
    return controller


class TestMinCoolingTarget:
    def test_follows_the_controller_when_it_has_computed(self):
        coordinator = make_coordinator(
            {CONF_COOLING_SUPPLY_MARGIN: 1.5}, controller=controller_with(19.5)
        )

        assert coordinator.effective_cooling_supply_temp == pytest.approx(19.5)
        assert coordinator.min_cooling_target == pytest.approx(21.0)

    def test_falls_back_to_the_static_value_before_the_first_computation(self):
        coordinator = make_coordinator(
            {CONF_COOLING_SUPPLY_TEMP: 18.0, CONF_COOLING_SUPPLY_MARGIN: 1.5},
            controller=controller_with(None),
        )

        assert coordinator.effective_cooling_supply_temp == pytest.approx(18.0)
        assert coordinator.min_cooling_target == pytest.approx(19.5)

    def test_is_none_when_neither_source_is_configured(self):
        coordinator = make_coordinator({}, controller=None)

        assert coordinator.effective_cooling_supply_temp is None
        assert coordinator.min_cooling_target is None

    def test_static_only_configuration_is_unchanged(self):
        coordinator = make_coordinator(
            {CONF_COOLING_SUPPLY_TEMP: 17.0, CONF_COOLING_SUPPLY_MARGIN: 2.0}, controller=None
        )

        assert coordinator.min_cooling_target == pytest.approx(19.0)

    def test_dynamic_value_tracks_the_controller_across_updates(self):
        controller = controller_with(21.0)
        coordinator = make_coordinator({CONF_COOLING_SUPPLY_MARGIN: 1.5}, controller=controller)

        assert coordinator.min_cooling_target == pytest.approx(22.5)
        controller.effective_cooling_supply_temp = 18.5
        assert coordinator.min_cooling_target == pytest.approx(20.0)


class TestSetupConflictWarning:
    def test_warns_when_static_and_dynamic_floors_disagree(self):
        from custom_components.adaptive_climate import check_cooling_supply_conflict

        message = check_cooling_supply_conflict(
            {
                CONF_COOLING_SUPPLY_TEMP: 16.0,
                CONF_WATER_TEMP_CONTROL: {
                    CONF_WATER_TEMP_COOLING: {
                        CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_cool",
                        CONF_WATER_TEMP_MIN_SUPPLY_TEMP: 18.0,
                    }
                },
            }
        )

        assert message is not None
        assert "16.0" in message and "18.0" in message

    def test_silent_when_the_values_agree(self):
        from custom_components.adaptive_climate import check_cooling_supply_conflict

        assert (
            check_cooling_supply_conflict(
                {
                    CONF_COOLING_SUPPLY_TEMP: 18.0,
                    CONF_WATER_TEMP_CONTROL: {
                        CONF_WATER_TEMP_COOLING: {
                            CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_cool",
                            CONF_WATER_TEMP_MIN_SUPPLY_TEMP: 18.0,
                        }
                    },
                }
            )
            is None
        )

    def test_silent_without_a_static_value(self):
        from custom_components.adaptive_climate import check_cooling_supply_conflict

        assert (
            check_cooling_supply_conflict(
                {
                    CONF_WATER_TEMP_CONTROL: {
                        CONF_WATER_TEMP_COOLING: {
                            CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_cool",
                            CONF_WATER_TEMP_MIN_SUPPLY_TEMP: 18.0,
                        }
                    }
                }
            )
            is None
        )

    def test_silent_without_water_temp_cooling(self):
        from custom_components.adaptive_climate import check_cooling_supply_conflict

        assert check_cooling_supply_conflict({CONF_COOLING_SUPPLY_TEMP: 18.0}) is None

    def test_reads_the_static_value_from_auto_mode_switching_too(self):
        from custom_components.adaptive_climate import check_cooling_supply_conflict

        message = check_cooling_supply_conflict(
            {
                "auto_mode_switching": {CONF_COOLING_SUPPLY_TEMP: 16.0},
                CONF_WATER_TEMP_CONTROL: {
                    CONF_WATER_TEMP_COOLING: {
                        CONF_WATER_TEMP_TARGET_ENTITY: "number.hp_cool",
                        CONF_WATER_TEMP_MIN_SUPPLY_TEMP: 18.0,
                    }
                },
            }
        )

        assert message is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_water_temp_clamp.py -v`
Expected: FAIL — `AttributeError: ... has no attribute 'effective_cooling_supply_temp'`

- [ ] **Step 3: Update `coordinator.py`**

Replace `min_cooling_target` (lines 337-343) with:

```python
    @property
    def effective_cooling_supply_temp(self) -> float | None:
        """Return the supply temperature that currently limits cooling setpoints.

        Prefers the water temperature controller's live effective value; falls
        back to the static ``cooling_supply_temp`` before the controller's first
        computation, or when water temperature control is not configured.

        With a dynamic supply temperature, a static clamp lets zones chase
        setpoints the water cannot deliver — integral windup plus spurious
        undershoot Ki boosts.
        """
        if self._water_temp_controller is not None:
            dynamic = self._water_temp_controller.effective_cooling_supply_temp
            if dynamic is not None:
                return dynamic
        return self.cooling_supply_temp

    @property
    def min_cooling_target(self) -> float | None:
        """Return the minimum cooling target (effective supply temp + margin), or None."""
        supply_temp = self.effective_cooling_supply_temp
        if supply_temp is None:
            return None
        return supply_temp + self.cooling_supply_margin
```

- [ ] **Step 4: Update `climate.py`**

In the cooling supply clamp block (line 1013), change the reported supply temperature so the `cooling_supply_clamp` status override shows the value actually in force:

```python
                    info["cooling_supply_clamp"] = {
                        "original_target": effective_target,
                        "effective_target": min_target,
                        "supply_temp": coordinator.effective_cooling_supply_temp,
                        "margin": coordinator.cooling_supply_margin,
                    }
```

- [ ] **Step 5: Add the setup warning to `__init__.py`**

Add next to `async_save_water_temp_state_now`:

```python
def check_cooling_supply_conflict(domain_config: dict[str, Any]) -> str | None:
    """Return a warning when the static and dynamic cooling floors disagree.

    ``cooling_supply_temp`` (static) and ``water_temp_control.cooling.min_supply_temp``
    (dynamic floor) describe the same physical limit.  Divergent values mean one
    of them is wrong.

    Args:
        domain_config: The validated ``adaptive_climate:`` domain config.

    Returns:
        A warning message naming both values, or None when there is no conflict.
    """
    water_temp = domain_config.get(CONF_WATER_TEMP_CONTROL) or {}
    cooling = water_temp.get(CONF_WATER_TEMP_COOLING)
    if not cooling:
        return None

    auto_mode = domain_config.get(CONF_AUTO_MODE_SWITCHING) or {}
    static = auto_mode.get(CONF_COOLING_SUPPLY_TEMP) or domain_config.get(CONF_COOLING_SUPPLY_TEMP)
    if static is None:
        return None

    dynamic = cooling.get(CONF_WATER_TEMP_MIN_SUPPLY_TEMP, DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP)
    if float(static) == float(dynamic):
        return None

    return (
        f"cooling_supply_temp ({static}°C) differs from "
        f"water_temp_control.cooling.min_supply_temp ({dynamic}°C). "
        "The dynamic value now drives min_cooling_target; the static one is only a "
        "fallback before the first computation. Align them to avoid surprises."
    )
```

Add the const imports `CONF_WATER_TEMP_MIN_SUPPLY_TEMP` and `DEFAULT_WATER_TEMP_MIN_SUPPLY_TEMP` if not already present, then call it right after the coordinator is created (line 478):

```python
    conflict = check_cooling_supply_conflict(domain_config)
    if conflict:
        _LOGGER.warning(conflict)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_water_temp_clamp.py tests/test_coordinator.py tests/test_climate.py tests/test_init.py -v`
Expected: PASS — new tests green, no regressions

- [ ] **Step 7: Lint and typecheck**

Run: `ruff check custom_components/adaptive_climate/coordinator.py custom_components/adaptive_climate/climate.py custom_components/adaptive_climate/__init__.py tests/test_water_temp_clamp.py && pyright custom_components/adaptive_climate/coordinator.py custom_components/adaptive_climate/climate.py custom_components/adaptive_climate/__init__.py`
Expected: no findings

- [ ] **Step 8: Commit**

```bash
git add custom_components/adaptive_climate/coordinator.py custom_components/adaptive_climate/climate.py custom_components/adaptive_climate/__init__.py tests/test_water_temp_clamp.py
git commit -m "feat(cooling): drive min_cooling_target from the dynamic supply temperature"
```

---

### Task 13: Diagnostic sensor

**Files:**
- Create: `custom_components/adaptive_climate/sensors/water_temp.py`
- Modify: `custom_components/adaptive_climate/sensor.py:122-157`
- Test: `tests/test_water_temp_sensor.py`

**Interfaces:**
- Consumes: `controller.diagnostics()` (Task 8), `coordinator.water_temp_controller` (Task 10).
- Produces: `WaterTempSupplySensor(hass)` — state is the current effective supply temperature; attributes are `mode`, `dew_point`, `binding_constraint`, `ramp_active`, `days_remaining`, `worst_source`. Created once, in the `system_sensors_created` block.

- [ ] **Step 1: Write the failing test**

Create `tests/test_water_temp_sensor.py`:

```python
"""Tests for the system-wide water temperature diagnostic sensor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.adaptive_climate.sensors.water_temp import WaterTempSupplySensor

DIAGNOSTICS = {
    "mode": "cooling",
    "effective": 19.5,
    "dew_point": 16.2,
    "binding_constraint": "dew_point",
    "ramp_active": False,
    "days_remaining": None,
    "worst_source": "kitchen",
}


def make_hass(controller=None):
    hass = MagicMock()
    coordinator = MagicMock()
    coordinator.water_temp_controller = controller
    hass.data = {"adaptive_climate": {"coordinator": coordinator}}
    return hass


def make_controller(diagnostics=None):
    controller = MagicMock()
    controller.diagnostics = MagicMock(return_value=diagnostics or DIAGNOSTICS)
    return controller


@pytest.mark.asyncio
async def test_state_is_the_effective_supply_temperature():
    sensor = WaterTempSupplySensor(make_hass(make_controller()))

    await sensor.async_update()

    assert sensor.native_value == pytest.approx(19.5)


@pytest.mark.asyncio
async def test_attributes_expose_the_full_diagnostic_payload():
    sensor = WaterTempSupplySensor(make_hass(make_controller()))

    await sensor.async_update()

    assert sensor.extra_state_attributes == {
        "mode": "cooling",
        "dew_point": 16.2,
        "binding_constraint": "dew_point",
        "ramp_active": False,
        "days_remaining": None,
        "worst_source": "kitchen",
    }


@pytest.mark.asyncio
async def test_ramp_diagnostics_are_surfaced():
    diagnostics = dict(DIAGNOSTICS, binding_constraint="ramp", ramp_active=True, days_remaining=3.5)
    sensor = WaterTempSupplySensor(make_hass(make_controller(diagnostics)))

    await sensor.async_update()

    assert sensor.extra_state_attributes["binding_constraint"] == "ramp"
    assert sensor.extra_state_attributes["ramp_active"] is True
    assert sensor.extra_state_attributes["days_remaining"] == 3.5


@pytest.mark.asyncio
async def test_sensor_is_unavailable_without_a_controller():
    sensor = WaterTempSupplySensor(make_hass(None))

    await sensor.async_update()

    assert sensor.native_value is None
    assert sensor.available is False


@pytest.mark.asyncio
async def test_a_failing_diagnostics_call_does_not_raise():
    controller = MagicMock()
    controller.diagnostics = MagicMock(side_effect=RuntimeError("boom"))
    sensor = WaterTempSupplySensor(make_hass(controller))

    await sensor.async_update()

    assert sensor.available is False


def test_sensor_identity_is_stable():
    sensor = WaterTempSupplySensor(make_hass(make_controller()))

    assert sensor.unique_id == "water_supply_temperature_target"
    assert sensor.name == "Water Supply Temperature Target"


def test_setup_creates_the_sensor_only_when_control_is_configured():
    """Guard used by sensor.py's system-wide block."""
    import inspect

    from custom_components.adaptive_climate import sensor as sensor_module

    source = inspect.getsource(sensor_module)
    assert "WaterTempSupplySensor" in source
    assert "water_temp_controller" in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_water_temp_sensor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '...sensors.water_temp'`

- [ ] **Step 3: Write minimal implementation**

Create `custom_components/adaptive_climate/sensors/water_temp.py`:

```python
"""System-wide diagnostic sensor for water temperature control."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

_LOGGER = logging.getLogger(__name__)


class WaterTempSupplySensor(SensorEntity):
    """Reports the current effective supply water temperature target."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the sensor.

        Args:
            hass: Home Assistant instance.
        """
        self.hass = hass
        self._attr_name = "Water Supply Temperature Target"
        self._attr_unique_id = "water_supply_temperature_target"
        self._attr_icon = "mdi:thermometer-water"
        self._attr_should_poll = False
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_available = False
        self._state: float | None = None
        self._attributes: dict[str, Any] = {}

    @property
    def _controller(self) -> Any | None:
        """Return the water temperature controller, or None."""
        from ..const import DOMAIN

        coordinator = self.hass.data.get(DOMAIN, {}).get("coordinator")
        if coordinator is None:
            return None
        return getattr(coordinator, "water_temp_controller", None)

    @property
    def native_value(self) -> float | None:
        """Return the current effective supply temperature."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the diagnostic breakdown."""
        return self._attributes

    async def async_update(self) -> None:
        """Refresh state from the controller's diagnostics payload."""
        controller = self._controller
        if controller is None:
            self._state = None
            self._attributes = {}
            self._attr_available = False
            return

        try:
            diagnostics = controller.diagnostics()
        except Exception:  # noqa: BLE001 - one bad sensor must not block the others
            _LOGGER.exception("Water temp diagnostics failed")
            self._state = None
            self._attributes = {}
            self._attr_available = False
            return

        self._state = diagnostics.get("effective")
        self._attributes = {
            "mode": diagnostics.get("mode"),
            "dew_point": diagnostics.get("dew_point"),
            "binding_constraint": diagnostics.get("binding_constraint"),
            "ramp_active": diagnostics.get("ramp_active", False),
            "days_remaining": diagnostics.get("days_remaining"),
            "worst_source": diagnostics.get("worst_source"),
        }
        self._attr_available = True
```

In `custom_components/adaptive_climate/sensor.py`, add the import next to the other sensor imports:

```python
from .sensors.water_temp import WaterTempSupplySensor
```

and inside the `if not hass.data[DOMAIN].get("system_sensors_created"):` block, immediately before `# Mark as created`:

```python
        # Create the water temperature diagnostic sensor when control is configured
        coordinator = hass.data[DOMAIN].get("coordinator")
        if coordinator is not None and getattr(coordinator, "water_temp_controller", None) is not None:
            sensors.append(WaterTempSupplySensor(hass))
            _LOGGER.info("WaterTempSupplySensor created")

```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_water_temp_sensor.py tests/test_comfort_sensors.py -v`
Expected: PASS — new tests green, existing sensor setup unaffected

- [ ] **Step 5: Lint and typecheck**

Run: `ruff check custom_components/adaptive_climate/sensors/water_temp.py custom_components/adaptive_climate/sensor.py tests/test_water_temp_sensor.py && pyright custom_components/adaptive_climate/sensors/water_temp.py custom_components/adaptive_climate/sensor.py`
Expected: no findings

- [ ] **Step 6: Commit**

```bash
git add custom_components/adaptive_climate/sensors/water_temp.py custom_components/adaptive_climate/sensor.py tests/test_water_temp_sensor.py
git commit -m "feat(sensor): add water supply temperature diagnostic sensor"
```

---

### Task 14: Full-suite verification and documentation

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: everything.
- Produces: updated architecture tables and test list; a note that the GitHub wiki needs the same change.

- [ ] **Step 1: Run the full suite**

Run: `pytest`
Expected: PASS — no failures, no errors

- [ ] **Step 2: Run the full lint / format / type gate**

Run: `ruff check custom_components/ tests/ && ruff format --check custom_components/ tests/ && pyright custom_components/adaptive_climate/`
Expected: no findings

- [ ] **Step 3: Verify no file exceeds the size ceiling**

Run: `find custom_components/adaptive_climate -name "*.py" -exec wc -l {} + | sort -rn | head -15`
Expected: no **newly created** file over 800 lines. `climate.py`, `const.py`, `coordinator.py`, `__init__.py`, `state_attributes.py` were already over before this work.

- [ ] **Step 4: Update the Core Modules table in `CLAUDE.md`**

Add these rows to the `### Core Modules` table:

```markdown
| `helpers/dew_point.py` | Pure Magnus-Tetens dew point calculation |
| `sensors/water_temp.py` | Water supply temperature diagnostic sensor |
```

- [ ] **Step 5: Update the Managers table in `CLAUDE.md`**

Add these rows to the `### Managers (managers/)` table:

```markdown
| `WaterTempController` | Supply water temp targets, ramps, write policy, interlocks |
| `DewPointScanner` | Worst-case indoor dew point across zones and extra sensors |
```

- [ ] **Step 6: Add a Water Temperature Control section to `CLAUDE.md`**

Insert after the `### Valve Actuation Time` section:

````markdown
### Water Temperature Control

Drives the heat pump's supply water temperature setpoints. Cooling is computed
from the worst-case indoor dew point; heating pushes a configured target. Both
ramp gradually when a mode resumes after a long idle period.

**Configuration (domain-level):**
```yaml
adaptive_climate:
  water_temp_control:
    idle_days: 7                    # ramp restarts after this many days inactive
    min_write_interval: 1800        # s between unsafe-direction writes
    condensation_sensor: binary_sensor.manifold_condensation
    cooling:
      target_entity: number.heatpump_cool_supply
      min_supply_temp: 18.0
      dew_point_margin: 2.0
      fallback_humidity: 65
      ramp_start: 22.0
      ramp_rate: 1.0
      extra_sensors:
        - humidity: sensor.manifold_rh
          temperature: sensor.manifold_temp
    heating:
      target_entity: number.heatpump_heat_supply
      target: 35.0                  # Range(20, 45); defaults to supply_temperature
      ramp_start: 25.0
      ramp_rate: 2.0
```

**Entity-level:** `exclude_from_dew_point: true` omits a zone's humidity from the scan.

**Warnings:**
- The heating half **overrides a heat pump's own weather-compensation curve** — only configure it if the pump runs a fixed setpoint.
- `supply_temperature` also feeds physics-based PID init; changing it changes both.
- Insulated supply pipework and manifold are a prerequisite for radiant cooling near the dew point.

**Dew point sources:** every COOL-mode zone with a `humidity_sensor` (minus
`exclude_from_dew_point` zones and zones whose HumidityDetector is
paused/stabilizing), plus configured `extra_sensors` pairs. Worst (highest) dew
point wins. RH is smoothed with a 20-min EMA per source. Implausible RH falls
back to `fallback_humidity`; implausible/missing temperature drops the source;
stale readings use `max(last_ema, fallback)`. With no real reading anywhere the
system is blind and floors at `max(min_supply_temp, 20.0)`.

**Targets:** `cooling = max(dew_point + margin, min_supply_temp)`,
`heating = target`. While a ramp is active the ramp bound applies instead.

**Ramps:** start when a mode becomes active after ≥ `idle_days` inactive. Heating
seeds from `max(ramp_start, current entity value)`; cooling always uses the
configured `ramp_start`. Heating and cooling track idle/ramp state independently.

**Write policy:** round to the entity's `step` toward the safe side (cooling up,
heating down), clamp to the entity's min/max, compare the post-clamp value.
Safe-direction changes write immediately; unsafe-direction changes must persist
for `min_write_interval`. Mode deactivation parks at `ramp_start`.

**Interlocks (cooling):** the condensation sensor being ON, or any COOL zone
reporting `open_window` / `contact_open`, forces an immediate park and holds for
30 minutes after the condition clears.

**Learning protection:** `coordinator.water_temp_learning_gate(mode)` is true
while a ramp is active and for one 60-min settling window after any write of
≥ 1.0 °C. While true, affected zones suppress cycle recording and undershoot
detection, surfaced as the existing `learning_grace` override.

**Cooling clamp:** `coordinator.min_cooling_target` reads the controller's live
effective supply temp (+ `cooling_supply_margin`), falling back to the static
`cooling_supply_temp` before the first computation.

**Persistence:** top-level `water_temp_state` key in the learning store
(additive, no `STORAGE_VERSION` bump). ISO timestamps for last-active and
ramp-start per mode, plus the last value written per entity.

**Diagnostic sensor:** `sensor.water_supply_temperature_target` — state is the
effective supply temp; attributes are `mode`, `dew_point`, `binding_constraint`
(`dew_point` / `min_supply` / `ramp` / `target` / `interlock` / `blind`),
`ramp_active`, `days_remaining`, `worst_source`.
````

- [ ] **Step 7: Update the Tests list in `CLAUDE.md`**

Append to the `## Tests` line: `` `test_dew_point.py`, `test_water_temp_config.py`, `test_water_temp_sources.py`, `test_water_temp_controller.py`, `test_water_temp_persistence.py`, `test_water_temp_wiring.py`, `test_water_temp_learning_gate.py`, `test_water_temp_clamp.py`, `test_water_temp_sensor.py` ``

- [ ] **Step 8: Note the wiki follow-up**

The project rule is "Update GitHub wiki alongside any doc changes." The wiki is
outside this repository, so it cannot be edited by this plan. Report to the
orchestrator: **the GitHub wiki needs the same Water Temperature Control page
added, mirroring the CLAUDE.md section from Step 6, including both configuration
warnings (heat-curve override, `supply_temperature` dual use) and the insulated-
pipework prerequisite.**

- [ ] **Step 9: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document water temperature control architecture and tests"
```

---

## Self-Review

**1. Spec coverage**

| Spec section | Task |
|---|---|
| Configuration (domain YAML, entity `exclude_from_dew_point`) | 2, 3 |
| Schema notes: optional halves, naming collision, `heating.target` fallback via domain `vol.All`, distinct target entities | 2 |
| Docs warnings (heat curve, dual-use `supply_temperature`, insulated pipework) | 14 |
| Dew point via Magnus-Tetens, `ValueError` on out-of-range RH, no `assert` | 1 |
| Sources scanned: COOL zones, exclusions, HumidityDetector paused, extra_sensors | 5 |
| Temperature pairing: device registry then climate attribute, log once, debug record | 5 (`temp_source` on each reading) |
| 20-min RH EMA | 5 |
| Plausibility, staleness, blind mode | 5, 6 |
| `dew_target = max(max(dew_points) + margin, min_supply_temp)` | 6 |
| Cooling/heating effective values; `get_zones_in_mode`; zone temps from entity attribute | 4, 6 |
| Ramp lifecycle, heating seed, independence, end condition, first run, `dt_util.utcnow()`, clamps | 6 |
| Write policy: safe rounding, entity clamp, post-clamp comparison, asymmetric dwell, `HeaterServiceCaller` shape, startup + 5-min timer with try/except, park on deactivation | 7, 8 |
| Interlocks: condensation sensor, COOL-zone overrides, immediate park, 30-min stabilization | 8 |
| Learning gate: ramp + ≥1.0 °C write, suppress cycle recording and undershoot, `learning_grace` surfacing | 8, 11 |
| Cooling clamp unification + static-value warning | 12 |
| Architecture table: file locations, ~15-line coordinator footprint, `async_cleanup` unsub, zone_data keys, persistence mirror of manifold, `_restored` gate | 5, 6, 8, 9, 10 |
| Diagnostics sensor | 13 |
| Testing section (every listed case) | 1, 2, 5, 6, 7, 8, 10, 11, 12, 13 |
| CLAUDE.md + wiki | 14 |

No gaps.

**2. Placeholder scan** — every code step carries real code; every test step carries real test functions; every run step names the command and the expected outcome. The one explicit deferral (the GitHub wiki) is called out as an out-of-repo report item, not a TODO in code.

**3. Type consistency** — names verified across tasks: `dew_point()`, `DewPointScanner.scan()`, `DewPointScan.{dew_point,worst_source,blind,readings}`, `SourceReading.{key,rh_pct,temp_c,dew_point_c,real,temp_source}`, `WaterTempController.{compute_targets,async_apply,_async_write,learning_gate,diagnostics,async_start,async_cleanup,get_state_for_persistence,restore_state,mark_restored,restored,effective_cooling_supply_temp,ramp_state,binding,enabled_modes,_utcnow}`, `ModeRampState.{last_active,ramp_started,ramp_start_value}`, `coordinator.{get_zones_in_mode,get_zone_current_temp,water_temp_controller,water_temp_learning_gate,effective_cooling_supply_temp,min_cooling_target,_setup_water_temp_control}`, `LearningDataStore.{async_load_water_temp_state,async_save_water_temp_state}`, `AdaptiveThermostat.water_temp_learning_gate_active`, `PauseDetector(water_temp_gate=...)`, `build_dew_point_zone_data`, `async_restore_water_temp_state`, `async_save_water_temp_state_now`, `check_cooling_supply_conflict`, `validate_water_temp_control`, `WaterTempSupplySensor`. Mode keys are `"cooling"` / `"heating"` everywhere, with `learning_gate` additionally accepting the `"cool"` / `"heat"` HVAC states.
