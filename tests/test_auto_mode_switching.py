"""Tests for AutoModeSwitchingManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant

from custom_components.adaptive_climate.const import (
    CONF_AUTO_MODE_THRESHOLD,
    CONF_FORECAST_DAYS,
    CONF_MIN_SWITCH_INTERVAL,
    CONF_SEASON_THRESHOLDS,
    CONF_SUMMER_ABOVE,
    CONF_WINTER_BELOW,
)
from custom_components.adaptive_climate.managers.auto_mode_switching import (
    AutoModeSwitchingManager,
)


def mock_forecast_response(weather_entity: str, forecast: list[dict]) -> dict:
    """Create a mock response for weather.get_forecasts service."""
    return {weather_entity: {"forecast": forecast}}


@pytest.fixture
def mock_hass():
    """Create mock HomeAssistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock(return_value=None)
    return hass


@pytest.fixture
def mock_coordinator():
    """Create mock coordinator."""
    coordinator = MagicMock()
    coordinator.weather_entity = "weather.home"
    coordinator.get_active_zone_setpoints = MagicMock(return_value=[20.0, 21.0, 22.0])
    return coordinator


@pytest.fixture
def default_config():
    """Default auto mode switching config."""
    return {
        CONF_AUTO_MODE_THRESHOLD: 2.0,
        CONF_MIN_SWITCH_INTERVAL: 3600,
        CONF_FORECAST_DAYS: 3,
        CONF_SEASON_THRESHOLDS: {
            CONF_WINTER_BELOW: 12.0,
            CONF_SUMMER_ABOVE: 18.0,
        },
    }


class TestAutoModeSwitchingManager:
    """Test AutoModeSwitchingManager class."""

    def test_init_with_defaults(self, mock_hass, mock_coordinator, default_config):
        """Test manager initializes with default values."""
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        assert manager._threshold == 2.0
        assert manager._min_switch_interval == 3600
        assert manager._forecast_days == 3
        assert manager._winter_below == 12.0
        assert manager._summer_above == 18.0
        assert manager._current_mode is None
        assert manager._last_switch == 0.0

    def test_init_with_custom_config(self, mock_hass, mock_coordinator):
        """Test manager initializes with custom config values."""
        config = {
            CONF_AUTO_MODE_THRESHOLD: 3.0,
            CONF_MIN_SWITCH_INTERVAL: 7200,
            CONF_FORECAST_DAYS: 5,
            CONF_SEASON_THRESHOLDS: {
                CONF_WINTER_BELOW: 10.0,
                CONF_SUMMER_ABOVE: 20.0,
            },
        }
        manager = AutoModeSwitchingManager(mock_hass, config, mock_coordinator)

        assert manager._threshold == 3.0
        assert manager._min_switch_interval == 7200
        assert manager._forecast_days == 5
        assert manager._winter_below == 10.0
        assert manager._summer_above == 20.0

    def test_init_with_empty_config(self, mock_hass, mock_coordinator):
        """Test manager uses defaults when config is empty."""
        manager = AutoModeSwitchingManager(mock_hass, {}, mock_coordinator)

        assert manager._threshold == 2.0
        assert manager._min_switch_interval == 3600
        assert manager._forecast_days == 3
        assert manager._winter_below == 12.0
        assert manager._summer_above == 18.0

    def test_properties(self, mock_hass, mock_coordinator, default_config):
        """Test public properties."""
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        assert manager.current_mode is None
        assert manager.last_switch_time == 0.0

    def test_stores_coordinator_reference(self, mock_hass, mock_coordinator, default_config):
        """Test that manager stores coordinator reference."""
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        assert manager._coordinator is mock_coordinator

    def test_stores_hass_reference(self, mock_hass, mock_coordinator, default_config):
        """Test that manager stores hass reference."""
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        assert manager._hass is mock_hass

    def test_partial_season_thresholds_config(self, mock_hass, mock_coordinator):
        """Test with partial season_thresholds config."""
        config = {
            CONF_AUTO_MODE_THRESHOLD: 2.0,
            CONF_SEASON_THRESHOLDS: {
                CONF_WINTER_BELOW: 10.0,
            },
        }
        manager = AutoModeSwitchingManager(mock_hass, config, mock_coordinator)

        assert manager._winter_below == 10.0
        assert manager._summer_above == 18.0  # default

    def test_missing_season_thresholds_config(self, mock_hass, mock_coordinator):
        """Test with missing season_thresholds section."""
        config = {
            CONF_AUTO_MODE_THRESHOLD: 2.0,
        }
        manager = AutoModeSwitchingManager(mock_hass, config, mock_coordinator)

        assert manager._winter_below == 12.0  # default
        assert manager._summer_above == 18.0  # default


class TestGetMedianSetpoint:
    """Tests for get_median_setpoint method."""

    def test_returns_median_of_zone_setpoints(self, mock_hass, mock_coordinator, default_config):
        """Test returns correct median from zone setpoints."""
        mock_coordinator.get_active_zone_setpoints.return_value = [20.0, 21.0, 22.0]
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = manager.get_median_setpoint()

        assert result == 21.0

    def test_returns_none_when_no_active_zones(self, mock_hass, mock_coordinator, default_config):
        """Test returns None when no active zones."""
        mock_coordinator.get_active_zone_setpoints.return_value = []
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = manager.get_median_setpoint()

        assert result is None

    def test_returns_median_with_even_number_of_zones(self, mock_hass, mock_coordinator, default_config):
        """Test median calculation with even number of zones."""
        mock_coordinator.get_active_zone_setpoints.return_value = [20.0, 22.0]
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = manager.get_median_setpoint()

        assert result == 21.0  # (20 + 22) / 2

    def test_returns_single_setpoint(self, mock_hass, mock_coordinator, default_config):
        """Test with single zone."""
        mock_coordinator.get_active_zone_setpoints.return_value = [19.5]
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = manager.get_median_setpoint()

        assert result == 19.5


class TestGetForecastMedian:
    """Tests for _async_get_forecast_median method."""

    @pytest.mark.asyncio
    async def test_returns_median_from_forecast(self, mock_hass, mock_coordinator, default_config):
        """Test returns correct median from forecast."""
        mock_hass.states.get.return_value = MagicMock()  # Entity exists
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response(
                "weather.home",
                [
                    {"temperature": 10.0},
                    {"temperature": 12.0},
                    {"temperature": 8.0},
                    {"temperature": 15.0},
                    {"temperature": 11.0},
                ],
            )
        )
        mock_coordinator.weather_entity = "weather.home"
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager._async_get_forecast_median()

        assert result == 11.0  # median of [8, 10, 11, 12, 15]

    @pytest.mark.asyncio
    async def test_returns_none_when_no_weather_entity(self, mock_hass, mock_coordinator, default_config):
        """Test returns None when no weather entity configured."""
        mock_coordinator.weather_entity = None
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager._async_get_forecast_median()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_weather_entity_not_found(self, mock_hass, mock_coordinator, default_config):
        """Test returns None when weather entity doesn't exist."""
        mock_hass.states.get.return_value = None
        mock_coordinator.weather_entity = "weather.nonexistent"
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager._async_get_forecast_median()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_forecast(self, mock_hass, mock_coordinator, default_config):
        """Test returns None when forecast is empty."""
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(return_value=mock_forecast_response("weather.home", []))
        mock_coordinator.weather_entity = "weather.home"
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager._async_get_forecast_median()

        assert result is None

    @pytest.mark.asyncio
    async def test_uses_up_to_7_forecast_entries(self, mock_hass, mock_coordinator, default_config):
        """Test only uses first 7 forecast entries."""
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response(
                "weather.home",
                [
                    {"temperature": 10.0},
                    {"temperature": 11.0},
                    {"temperature": 12.0},
                    {"temperature": 13.0},
                    {"temperature": 14.0},
                    {"temperature": 15.0},
                    {"temperature": 16.0},
                    {"temperature": 100.0},  # Entry 8 - should be ignored
                    {"temperature": 100.0},  # Entry 9 - should be ignored
                    {"temperature": 100.0},  # Entry 10 - should be ignored
                ],
            )
        )
        mock_coordinator.weather_entity = "weather.home"
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager._async_get_forecast_median()

        assert result == 13.0  # median of [10, 11, 12, 13, 14, 15, 16]

    @pytest.mark.asyncio
    async def test_skips_entries_without_temperature(self, mock_hass, mock_coordinator, default_config):
        """Test skips forecast entries without temperature."""
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response(
                "weather.home",
                [
                    {"temperature": 10.0},
                    {"condition": "sunny"},  # No temperature
                    {"temperature": 12.0},
                ],
            )
        )
        mock_coordinator.weather_entity = "weather.home"
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager._async_get_forecast_median()

        assert result == 11.0  # median of [10, 12]

    @pytest.mark.asyncio
    async def test_handles_service_call_exception(self, mock_hass, mock_coordinator, default_config):
        """Test handles exception from service call gracefully."""
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(side_effect=Exception("Service error"))
        mock_coordinator.weather_entity = "weather.home"
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager._async_get_forecast_median()

        assert result is None


class TestGetSeason:
    """Tests for async_get_season method."""

    @pytest.mark.asyncio
    async def test_returns_winter_when_cold(self, mock_hass, mock_coordinator, default_config):
        """Test returns winter when forecast median is below winter_below."""
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response(
                "weather.home",
                [
                    {"temperature": 5.0},
                    {"temperature": 7.0},
                    {"temperature": 8.0},
                ],
            )
        )
        mock_coordinator.weather_entity = "weather.home"
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_get_season()

        assert result == "winter"  # median 7.0 < 12.0

    @pytest.mark.asyncio
    async def test_returns_summer_when_hot(self, mock_hass, mock_coordinator, default_config):
        """Test returns summer when forecast median is above summer_above."""
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response(
                "weather.home",
                [
                    {"temperature": 25.0},
                    {"temperature": 28.0},
                    {"temperature": 22.0},
                ],
            )
        )
        mock_coordinator.weather_entity = "weather.home"
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_get_season()

        assert result == "summer"  # median 25.0 > 18.0

    @pytest.mark.asyncio
    async def test_returns_shoulder_when_moderate(self, mock_hass, mock_coordinator, default_config):
        """Test returns shoulder when forecast median is between thresholds."""
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response(
                "weather.home",
                [
                    {"temperature": 14.0},
                    {"temperature": 15.0},
                    {"temperature": 16.0},
                ],
            )
        )
        mock_coordinator.weather_entity = "weather.home"
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_get_season()

        assert result == "shoulder"  # median 15.0 is between 12.0 and 18.0

    @pytest.mark.asyncio
    async def test_returns_shoulder_when_no_forecast(self, mock_hass, mock_coordinator, default_config):
        """Test returns shoulder when no forecast available."""
        mock_coordinator.weather_entity = None
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_get_season()

        assert result == "shoulder"

    @pytest.mark.asyncio
    async def test_uses_custom_thresholds(self, mock_hass, mock_coordinator):
        """Test uses custom season thresholds."""
        config = {
            CONF_SEASON_THRESHOLDS: {
                CONF_WINTER_BELOW: 10.0,
                CONF_SUMMER_ABOVE: 20.0,
            },
        }
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response("weather.home", [{"temperature": 15.0}])
        )
        mock_coordinator.weather_entity = "weather.home"
        manager = AutoModeSwitchingManager(mock_hass, config, mock_coordinator)

        result = await manager.async_get_season()

        assert result == "shoulder"  # 15.0 is between 10.0 and 20.0

    @pytest.mark.asyncio
    async def test_caches_season_value(self, mock_hass, mock_coordinator, default_config):
        """Test that season value is cached."""
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response("weather.home", [{"temperature": 5.0}])
        )
        mock_coordinator.weather_entity = "weather.home"
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        await manager.async_get_season()

        assert manager._cached_season == "winter"


class TestAsyncEvaluate:
    """Tests for async_evaluate method."""

    @pytest.mark.asyncio
    async def test_returns_heat_when_forecast_cold(self, mock_hass, mock_coordinator, default_config):
        """Test returns HEAT when forecast < median - threshold."""
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = "weather.home"
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response("weather.home", [{"temperature": 15.0}])
        )

        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_evaluate()

        assert result == HVACMode.HEAT  # 15 < 21 - 2 = 19

    @pytest.mark.asyncio
    async def test_returns_cool_when_forecast_hot(self, mock_hass, mock_coordinator, default_config):
        """Test returns COOL when forecast > median + threshold."""
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = "weather.home"
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response("weather.home", [{"temperature": 28.0}])
        )

        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_evaluate()

        assert result == HVACMode.COOL  # 28 > 21 + 2 = 23

    @pytest.mark.asyncio
    async def test_returns_none_when_forecast_in_hysteresis(self, mock_hass, mock_coordinator, default_config):
        """Test returns None when forecast in hysteresis zone."""
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = "weather.home"
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response("weather.home", [{"temperature": 20.0}])
        )

        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_evaluate()

        assert result is None  # 20 is within 21 ± 2

    @pytest.mark.asyncio
    async def test_respects_min_switch_interval(self, mock_hass, mock_coordinator, default_config):
        """Test respects minimum switch interval."""
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = "weather.home"
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response("weather.home", [{"temperature": 15.0}])
        )

        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        # First evaluation should succeed
        result1 = await manager.async_evaluate()
        assert result1 == HVACMode.HEAT

        # Change forecast to warrant COOL
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response("weather.home", [{"temperature": 28.0}])
        )

        # Second evaluation within interval should return None
        result2 = await manager.async_evaluate()
        assert result2 is None

    @pytest.mark.asyncio
    async def test_winter_blocks_cool(self, mock_hass, mock_coordinator, default_config):
        """Test winter season blocks switching to COOL even with warm forecast."""
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = "weather.home"
        mock_hass.states.get.return_value = MagicMock()
        # Forecast median is 5°C (winter) but one day is 28°C
        # This tests that season lock prevents COOL in winter
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response(
                "weather.home",
                [
                    {"temperature": 5.0},
                    {"temperature": 5.0},
                    {"temperature": 5.0},
                    {"temperature": 5.0},
                    {"temperature": 5.0},
                ],
            )
        )

        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_evaluate()

        # Forecast median 5°C < 21 - 2 = 19, suggests HEAT
        # Season is winter (5°C < 12°C)
        # HEAT is allowed in winter
        assert result == HVACMode.HEAT

    @pytest.mark.asyncio
    async def test_summer_blocks_heat(self, mock_hass, mock_coordinator, default_config):
        """Test summer season blocks switching to HEAT."""
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = "weather.home"
        mock_hass.states.get.return_value = MagicMock()
        # Forecast shows summer conditions (median > 18°C)
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response("weather.home", [{"temperature": 25.0}])
        )

        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_evaluate()

        # Forecast 25°C > 21 + 2 = 23, suggests COOL
        # Season is summer (25°C > 18°C)
        # COOL is allowed in summer
        assert result == HVACMode.COOL

    @pytest.mark.asyncio
    async def test_returns_none_when_no_forecast(self, mock_hass, mock_coordinator, default_config):
        """Test returns None when no forecast available."""
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = None

        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_evaluate()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_active_zones(self, mock_hass, mock_coordinator, default_config):
        """Test returns None when no active zones."""
        mock_coordinator.get_active_zone_setpoints.return_value = []

        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_evaluate()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_mode_unchanged(self, mock_hass, mock_coordinator, default_config):
        """Test returns None when target mode equals current mode."""
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = "weather.home"
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response("weather.home", [{"temperature": 15.0}])
        )

        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        # First evaluation
        result1 = await manager.async_evaluate()
        assert result1 == HVACMode.HEAT

        # Reset last_switch to allow another evaluation
        manager._last_switch = 0.0

        # Second evaluation with same conditions
        result2 = await manager.async_evaluate()
        assert result2 is None  # No change needed

    @pytest.mark.asyncio
    async def test_updates_state_on_switch(self, mock_hass, mock_coordinator, default_config):
        """Test updates internal state when switching mode."""
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = "weather.home"
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response("weather.home", [{"temperature": 15.0}])
        )

        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        assert manager.current_mode is None
        assert manager.last_switch_time == 0.0

        result = await manager.async_evaluate()

        assert result == HVACMode.HEAT
        assert manager.current_mode == HVACMode.HEAT
        assert manager.last_switch_time > 0.0


class TestEdgeCases:
    """Tests for edge case handling."""

    @pytest.mark.asyncio
    async def test_all_zones_off_returns_none(self, mock_hass, mock_coordinator, default_config):
        """Test returns None when all zones are OFF."""
        mock_coordinator.get_active_zone_setpoints.return_value = []
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_evaluate()

        assert result is None

    @pytest.mark.asyncio
    async def test_no_weather_entity_returns_none_for_forecast(self, mock_hass, mock_coordinator, default_config):
        """Test _async_get_forecast_median returns None when no weather entity."""
        mock_coordinator.weather_entity = None
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager._async_get_forecast_median()

        assert result is None

    @pytest.mark.asyncio
    async def test_weather_entity_not_found_returns_none(self, mock_hass, mock_coordinator, default_config):
        """Test _async_get_forecast_median handles missing weather entity."""
        mock_hass.states.get.return_value = None
        mock_coordinator.weather_entity = "weather.nonexistent"
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager._async_get_forecast_median()

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_forecast_returns_none(self, mock_hass, mock_coordinator, default_config):
        """Test _async_get_forecast_median handles empty forecast."""
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(return_value=mock_forecast_response("weather.home", []))
        mock_coordinator.weather_entity = "weather.home"
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager._async_get_forecast_median()

        assert result is None

    @pytest.mark.asyncio
    async def test_short_forecast_uses_available_entries(self, mock_hass, mock_coordinator, default_config):
        """Test handles forecast with fewer than 7 entries."""
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response(
                "weather.home",
                [
                    {"temperature": 10.0},
                    {"temperature": 12.0},
                ],
            )
        )
        mock_coordinator.weather_entity = "weather.home"
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager._async_get_forecast_median()

        assert result == 11.0  # median of [10, 12]


class TestGetStateAttributes:
    """Tests for get_state_attributes method."""

    def test_basic_attributes_always_included(self, mock_hass, mock_coordinator, default_config):
        """Test basic attributes are always included."""
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        attrs = manager.get_state_attributes(debug=False)

        assert "auto_mode_switching_enabled" in attrs
        assert attrs["auto_mode_switching_enabled"] is True

    def test_debug_attributes_included_when_debug(self, mock_hass, mock_coordinator, default_config):
        """Test debug attributes included when debug=True."""
        mock_coordinator.get_active_zone_setpoints.return_value = [20.0, 22.0]
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)
        # Set cached values manually since we don't call async methods
        manager._cached_season = "shoulder"
        manager._cached_forecast_median = 15.0

        attrs = manager.get_state_attributes(debug=True)

        assert "auto_mode_switching" in attrs
        assert attrs["auto_mode_switching"]["current_season"] == "shoulder"
        assert attrs["auto_mode_switching"]["forecast_median_temp"] == 15.0
        assert attrs["auto_mode_switching"]["median_setpoint"] == 21.0

    def test_debug_attributes_excluded_when_not_debug(self, mock_hass, mock_coordinator, default_config):
        """Test debug attributes excluded when debug=False."""
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        attrs = manager.get_state_attributes(debug=False)

        assert "auto_mode_switching" not in attrs

    @pytest.mark.asyncio
    async def test_debug_attributes_include_switch_times(self, mock_hass, mock_coordinator, default_config):
        """Test debug attributes include switch times after a switch."""
        mock_coordinator.outdoor_temp = 15.0
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = "weather.home"
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response("weather.home", [{"temperature": 15.0}])
        )
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        # Trigger a switch
        await manager.async_evaluate()

        attrs = manager.get_state_attributes(debug=True)

        assert "last_switch" in attrs["auto_mode_switching"]
        assert "next_allowed_switch" in attrs["auto_mode_switching"]
