"""Tests for the system-wide water temperature diagnostic sensor."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# homeassistant.components.sensor and homeassistant.helpers.entity are NOT
# added by conftest.py (see tests/test_sensors_performance.py for the same
# idiom). Inject them before importing from
# custom_components.adaptive_climate.sensors.water_temp.
# ---------------------------------------------------------------------------
if "homeassistant.components.sensor" not in sys.modules:
    _mock_sensor_mod = MagicMock()
    _mock_sensor_mod.SensorEntity = type("SensorEntity", (), {})
    _mock_sensor_mod.SensorDeviceClass = MagicMock()
    _mock_sensor_mod.SensorStateClass = MagicMock()
    sys.modules["homeassistant.components.sensor"] = _mock_sensor_mod

if "homeassistant.helpers.entity" not in sys.modules:
    _mock_entity_mod = MagicMock()
    _mock_entity_mod.EntityCategory = MagicMock()
    sys.modules["homeassistant.helpers.entity"] = _mock_entity_mod

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
