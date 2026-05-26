"""Focused energy sensor tests: currency parsing, unit conversions, BTU, currency locking.

Covers gaps not in test_energy.py:
- _parse_iso_currency with symbols ($, €, £, ¥, kr, Ft, zł) and unknown values
- UNIT_CONVERSIONS: BTU, Wh, MWh, therm correctness
- WeeklyCostSensor with BTU meter reading
- WeeklyCostSensor currency locking behaviour (freeze after first read)
- Unknown energy unit raises ValueError → graceful reset
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# homeassistant.components.sensor is NOT added by conftest.py.
# It must be injected before any import from custom_components.adaptive_climate.sensors.
# ---------------------------------------------------------------------------
if "homeassistant.components.sensor" not in sys.modules:
    _mock_sensor_mod = MagicMock()
    # Give SensorEntity a concrete (non-mock) base so class definitions work.
    _mock_sensor_mod.SensorEntity = type("SensorEntity", (), {})
    _mock_sensor_mod.SensorDeviceClass = MagicMock()
    _mock_sensor_mod.SensorStateClass = MagicMock()
    sys.modules["homeassistant.components.sensor"] = _mock_sensor_mod

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from custom_components.adaptive_climate.sensors.energy import (
    _parse_iso_currency,
    WeeklyCostSensor,
)
from custom_components.adaptive_climate.analytics.energy import UNIT_CONVERSIONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc(year=2025, month=6, day=1, hour=12, minute=0, second=0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def _make_sensor(mock_hass, *, cost_entity=None) -> WeeklyCostSensor:
    return WeeklyCostSensor(
        hass=mock_hass,
        energy_meter_entity="sensor.energy_meter",
        energy_cost_entity=cost_entity,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_hass():
    hass = Mock()
    hass.states = Mock()
    hass.data = {}
    return hass


@pytest.fixture
def sensor(mock_hass):
    return _make_sensor(mock_hass)


# ---------------------------------------------------------------------------
# _parse_iso_currency
# ---------------------------------------------------------------------------


class TestParseIsoCurrency:
    """_parse_iso_currency converts symbols and ISO codes to ISO 4217."""

    def test_dollar_to_usd(self):
        assert _parse_iso_currency("$") == "USD"

    def test_euro_to_eur(self):
        assert _parse_iso_currency("€") == "EUR"

    def test_pound_to_gbp(self):
        assert _parse_iso_currency("£") == "GBP"

    def test_yen_to_jpy(self):
        assert _parse_iso_currency("¥") == "JPY"

    def test_kr_to_sek(self):
        assert _parse_iso_currency("kr") == "SEK"

    def test_ft_to_huf(self):
        assert _parse_iso_currency("Ft") == "HUF"

    def test_zloty_to_pln(self):
        assert _parse_iso_currency("zł") == "PLN"

    def test_iso_code_passthrough(self):
        assert _parse_iso_currency("USD") == "USD"

    def test_lowercase_iso_normalised(self):
        assert _parse_iso_currency("eur") == "EUR"

    def test_mixed_case_iso(self):
        assert _parse_iso_currency("Gbp") == "GBP"

    def test_unknown_symbol_returns_none(self):
        assert _parse_iso_currency("FAKE_CURRENCY") is None

    def test_empty_string_returns_none(self):
        assert _parse_iso_currency("") is None

    def test_strips_surrounding_whitespace(self):
        assert _parse_iso_currency("  USD  ") == "USD"

    def test_chf_passthrough(self):
        assert _parse_iso_currency("CHF") == "CHF"

    def test_swiss_franc_symbol(self):
        assert _parse_iso_currency("Fr") == "CHF"


# ---------------------------------------------------------------------------
# UNIT_CONVERSIONS correctness
# ---------------------------------------------------------------------------


class TestUnitConversions:
    """Energy unit conversion constants match published values."""

    def test_kwh_is_unity(self):
        assert UNIT_CONVERSIONS["KWH"] == 1.0

    def test_wh_to_kwh(self):
        """1 Wh = 0.001 kWh."""
        assert UNIT_CONVERSIONS["WH"] == pytest.approx(0.001)

    def test_mwh_to_kwh(self):
        """1 MWh = 1 000 kWh."""
        assert UNIT_CONVERSIONS["MWH"] == pytest.approx(1000.0)

    def test_gj_to_kwh(self):
        """1 GJ = 277.778 kWh."""
        assert UNIT_CONVERSIONS["GJ"] == pytest.approx(277.778, rel=1e-4)

    def test_btu_to_kwh(self):
        """1 BTU ≈ 0.000293071 kWh."""
        assert UNIT_CONVERSIONS["BTU"] == pytest.approx(0.000293071, rel=1e-4)

    def test_therm_to_kwh(self):
        """1 therm = 29.3071 kWh (100 000 BTU)."""
        assert UNIT_CONVERSIONS["THERM"] == pytest.approx(29.3071, rel=1e-4)

    def test_mmbtu_to_kwh(self):
        """1 MMBtu = 293.071 kWh (1 000 000 BTU)."""
        assert UNIT_CONVERSIONS["MMBTU"] == pytest.approx(293.071, rel=1e-4)

    def test_10k_btu_is_approx_2930_wh(self):
        """10 000 BTU ≈ 2.93071 kWh — space-heater sanity check."""
        result = 10_000 * UNIT_CONVERSIONS["BTU"]
        assert result == pytest.approx(2.93071, rel=1e-4)

    def test_therm_equals_100k_btu(self):
        """1 therm must equal 100 000 BTU within floating-point tolerance."""
        assert UNIT_CONVERSIONS["THERM"] == pytest.approx(100_000 * UNIT_CONVERSIONS["BTU"], rel=1e-4)


# ---------------------------------------------------------------------------
# WeeklyCostSensor — BTU / Wh meter readings
# ---------------------------------------------------------------------------


class TestWeeklySensorUnitConversion:
    """WeeklyCostSensor correctly converts meter readings to kWh before delta calc."""

    def _run_update(self, sensor, now):
        with patch("custom_components.adaptive_climate.sensors.energy.dt_util") as mock_dt:
            mock_dt.utcnow.return_value = now
            mock_dt.now.return_value = now
            asyncio.run(sensor.async_update())

    def test_btu_meter_delta_calculation(self, sensor, mock_hass):
        """200 000 BTU − 100 000 BTU → 100 000 × BTU_FACTOR kWh delta."""
        now = _utc()
        btu_factor = UNIT_CONVERSIONS["BTU"]
        sensor._week_start_reading = 100_000 * btu_factor
        sensor._week_start_timestamp = now

        meter_state = Mock()
        meter_state.state = "200000"
        meter_state.attributes = {"unit_of_measurement": "BTU"}
        mock_hass.states.get = Mock(side_effect=lambda eid: meter_state if eid == "sensor.energy_meter" else None)

        self._run_update(sensor, now)

        expected_delta = 100_000 * btu_factor
        assert sensor._weekly_energy_kwh == pytest.approx(expected_delta, rel=1e-4)

    def test_btu_first_reading_initialises_in_kwh(self, sensor, mock_hass):
        """First BTU reading stores week_start_reading in kWh (not raw BTU)."""
        now = _utc()
        meter_state = Mock()
        meter_state.state = "500000"
        meter_state.attributes = {"unit_of_measurement": "BTU"}
        mock_hass.states.get = Mock(side_effect=lambda eid: meter_state if eid == "sensor.energy_meter" else None)

        self._run_update(sensor, now)

        expected_kwh = 500_000 * UNIT_CONVERSIONS["BTU"]
        assert sensor._week_start_reading == pytest.approx(expected_kwh, rel=1e-4)
        assert sensor._weekly_energy_kwh == pytest.approx(0.0)

    def test_wh_meter_delta(self, sensor, mock_hass):
        """Wh meter: 50 000 Wh − 40 000 Wh = 10 kWh delta."""
        now = _utc()
        wh_factor = UNIT_CONVERSIONS["WH"]
        sensor._week_start_reading = 40_000 * wh_factor  # 40 kWh
        sensor._week_start_timestamp = now

        meter_state = Mock()
        meter_state.state = "50000"
        meter_state.attributes = {"unit_of_measurement": "Wh"}
        mock_hass.states.get = Mock(side_effect=lambda eid: meter_state if eid == "sensor.energy_meter" else None)

        self._run_update(sensor, now)

        assert sensor._weekly_energy_kwh == pytest.approx(10.0, rel=1e-6)

    def test_unknown_unit_resets_value_to_zero(self, sensor, mock_hass):
        """Meter with unsupported unit: error handled gracefully, _value = 0."""
        now = _utc()
        sensor._week_start_reading = 100.0
        sensor._week_start_timestamp = now

        meter_state = Mock()
        meter_state.state = "123.0"
        meter_state.attributes = {"unit_of_measurement": "FURLONGS"}
        mock_hass.states.get = Mock(side_effect=lambda eid: meter_state if eid == "sensor.energy_meter" else None)

        self._run_update(sensor, now)

        assert sensor._value == 0.0


# ---------------------------------------------------------------------------
# WeeklyCostSensor — currency locking
# ---------------------------------------------------------------------------


class TestCurrencyLocking:
    """Currency is frozen on first successful parse to prevent HA stat invalidation."""

    def _run_update(self, sensor, now):
        with patch("custom_components.adaptive_climate.sensors.energy.dt_util") as mock_dt:
            mock_dt.utcnow.return_value = now
            mock_dt.now.return_value = now
            asyncio.run(sensor.async_update())

    def test_currency_locked_after_first_read(self, mock_hass):
        """Currency symbol in cost entity UoM is parsed and locked on first update."""
        now = _utc()
        s = _make_sensor(mock_hass, cost_entity="sensor.energy_price")
        s._week_start_reading = 0.0
        s._week_start_timestamp = now

        meter_state = Mock()
        meter_state.state = "10.0"
        meter_state.attributes = {"unit_of_measurement": "kWh"}

        price_state = Mock()
        price_state.state = "0.30"
        price_state.attributes = {"unit_of_measurement": "$/kWh"}

        mock_hass.states.get = Mock(side_effect=lambda eid: meter_state if "meter" in eid else price_state)

        self._run_update(s, now)

        assert s._currency_locked is True
        assert s._currency == "USD"

    def test_currency_not_changed_after_lock(self, mock_hass):
        """Once locked to USD, a subsequent EUR signal is silently ignored."""
        now = _utc()
        s = _make_sensor(mock_hass, cost_entity="sensor.energy_price")
        s._week_start_reading = 0.0
        s._week_start_timestamp = now
        s._currency = "USD"
        s._currency_locked = True

        meter_state = Mock()
        meter_state.state = "50.0"
        meter_state.attributes = {"unit_of_measurement": "kWh"}

        price_state = Mock()
        price_state.state = "0.25"
        price_state.attributes = {"unit_of_measurement": "EUR/kWh"}

        mock_hass.states.get = Mock(side_effect=lambda eid: meter_state if "meter" in eid else price_state)

        self._run_update(s, now)

        assert s._currency == "USD"

    def test_unknown_currency_leaves_default_unlocked(self, mock_hass):
        """Unrecognised UoM keeps sensor at default EUR without locking."""
        now = _utc()
        s = _make_sensor(mock_hass, cost_entity="sensor.energy_price")
        s._week_start_reading = 0.0
        s._week_start_timestamp = now

        meter_state = Mock()
        meter_state.state = "10.0"
        meter_state.attributes = {"unit_of_measurement": "kWh"}

        price_state = Mock()
        price_state.state = "0.30"
        price_state.attributes = {"unit_of_measurement": "WIDGETS/kWh"}

        mock_hass.states.get = Mock(side_effect=lambda eid: meter_state if "meter" in eid else price_state)

        self._run_update(s, now)

        # Currency stays at the default "EUR" (initial value), not locked
        assert s._currency_locked is False
        assert s._currency == "EUR"

    def test_euro_symbol_locks_to_eur(self, mock_hass):
        """€ symbol in UoM should lock currency to EUR."""
        now = _utc()
        s = _make_sensor(mock_hass, cost_entity="sensor.energy_price")
        s._week_start_reading = 0.0
        s._week_start_timestamp = now

        meter_state = Mock()
        meter_state.state = "5.0"
        meter_state.attributes = {"unit_of_measurement": "kWh"}

        price_state = Mock()
        price_state.state = "0.28"
        price_state.attributes = {"unit_of_measurement": "€/kWh"}

        mock_hass.states.get = Mock(side_effect=lambda eid: meter_state if "meter" in eid else price_state)

        self._run_update(s, now)

        assert s._currency_locked is True
        assert s._currency == "EUR"
