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
    coordinator.outdoor_temp = None  # Default: no fallback outdoor temp
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
        """Test returns correct median from forecast using forecast_days entries.

        default_config has CONF_FORECAST_DAYS=3, so only the first 3 entries are used.
        """
        mock_hass.states.get.return_value = MagicMock()  # Entity exists
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response(
                "weather.home",
                [
                    {"temperature": 10.0},
                    {"temperature": 12.0},
                    {"temperature": 8.0},
                    {"temperature": 15.0},  # Entry 4 - ignored (forecast_days=3)
                    {"temperature": 11.0},  # Entry 5 - ignored
                ],
            )
        )
        mock_coordinator.weather_entity = "weather.home"
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager._async_get_forecast_median()

        assert result == 10.0  # median of [10, 12, 8] (first 3 entries)

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
    async def test_uses_forecast_days_config(self, mock_hass, mock_coordinator, default_config):
        """Test only uses first forecast_days entries (default_config sets CONF_FORECAST_DAYS=3)."""
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response(
                "weather.home",
                [
                    {"temperature": 10.0},
                    {"temperature": 11.0},
                    {"temperature": 12.0},
                    {"temperature": 100.0},  # Entry 4 - must be ignored (forecast_days=3)
                    {"temperature": 100.0},  # Entry 5 - must be ignored
                ],
            )
        )
        mock_coordinator.weather_entity = "weather.home"
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager._async_get_forecast_median()

        assert result == 11.0  # median of [10, 11, 12]

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
        """Test respects minimum switch interval.

        H06: mark_switched() is responsible for recording the switch; only after
        it is called does async_evaluate respect the rate-limit interval.
        """
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

        # Simulate coordinator calling mark_switched after applying to zones (H06)
        manager.mark_switched(result1)

        # Change forecast to warrant COOL
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response("weather.home", [{"temperature": 28.0}])
        )

        # Second evaluation within interval should return None (rate-limited)
        result2 = await manager.async_evaluate()
        assert result2 is None

    @pytest.mark.asyncio
    async def test_winter_allows_heat(self, mock_hass, mock_coordinator, default_config):
        """Test winter season allows switching to HEAT (the permitted direction)."""
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = "weather.home"
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response(
                "weather.home",
                [{"temperature": 5.0}, {"temperature": 5.0}, {"temperature": 5.0}],
            )
        )

        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_evaluate()

        # Forecast median 5°C < 21 - 2 = 19, suggests HEAT
        # Season is winter (5°C < 12°C) — HEAT is allowed
        assert result == HVACMode.HEAT

    @pytest.mark.asyncio
    async def test_winter_blocks_cool(self, mock_hass, mock_coordinator):
        """Test winter season blocks switching to COOL even when forecast is warm."""
        mock_coordinator.get_active_zone_setpoints.return_value = [16.0]
        mock_coordinator.weather_entity = "weather.home"
        mock_hass.states.get.return_value = MagicMock()
        # Season is winter (median 5°C < 12°C) but forecast is above setpoint+threshold
        # so without the season lock it would suggest COOL.
        # winter_below=12, summer_above=18 — but median 5°C qualifies as winter.
        # We force a scenario where season=winter but target_mode=COOL:
        # setpoint=16, forecast=19 > 16+2=18 → would suggest COOL, blocked by winter lock.
        # Override winter_below to ensure 5°C median counts as winter.
        # Use a forecast that yields median > setpoint+threshold.
        # That's impossible with winter_below=12: if median > summer_above=18 it's summer.
        # So we set winter_below=30 to make median=5 still "winter" despite being above setpoint.
        mock_coordinator.get_active_zone_setpoints.return_value = [10.0]
        # Forecast median 5°C is winter, 5°C < 10 - 2 = 8 → HEAT suggestion.
        # Need median > setpoint + threshold to suggest COOL while still being winter.
        # That's impossible with winter_below=12: if median > summer_above=18 it's summer.
        # So we set winter_below=30 to make median=5 still "winter" despite being above setpoint.
        config_winter_lock = {
            CONF_AUTO_MODE_THRESHOLD: 2.0,
            CONF_MIN_SWITCH_INTERVAL: 3600,
            CONF_FORECAST_DAYS: 3,
            CONF_SEASON_THRESHOLDS: {
                CONF_WINTER_BELOW: 30.0,  # Everything below 30°C is "winter"
                CONF_SUMMER_ABOVE: 50.0,  # Unreachable summer threshold
            },
        }
        mock_coordinator.get_active_zone_setpoints.return_value = [15.0]
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response(
                "weather.home",
                [{"temperature": 20.0}, {"temperature": 20.0}, {"temperature": 20.0}],
            )
        )
        manager = AutoModeSwitchingManager(mock_hass, config_winter_lock, mock_coordinator)

        result = await manager.async_evaluate()

        # Forecast median 20°C > 15 + 2 = 17 → suggests COOL
        # Season is winter (20°C < winter_below=30) → COOL is blocked
        assert result is None

    @pytest.mark.asyncio
    async def test_summer_allows_cool(self, mock_hass, mock_coordinator, default_config):
        """Test summer season allows switching to COOL (the permitted direction)."""
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = "weather.home"
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response(
                "weather.home",
                [{"temperature": 25.0}, {"temperature": 25.0}, {"temperature": 25.0}],
            )
        )

        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_evaluate()

        # Forecast 25°C > 21 + 2 = 23, suggests COOL
        # Season is summer (25°C > 18°C) — COOL is allowed
        assert result == HVACMode.COOL

    @pytest.mark.asyncio
    async def test_summer_blocks_heat(self, mock_hass, mock_coordinator):
        """Test summer season blocks switching to HEAT even when forecast is cold."""
        # Use a config where everything above 0°C is "summer" so a cold forecast
        # still triggers season=summer, but forecast < setpoint - threshold → HEAT suggestion.
        config_summer_lock = {
            CONF_AUTO_MODE_THRESHOLD: 2.0,
            CONF_MIN_SWITCH_INTERVAL: 3600,
            CONF_FORECAST_DAYS: 3,
            CONF_SEASON_THRESHOLDS: {
                CONF_WINTER_BELOW: -50.0,  # Unreachable winter threshold
                CONF_SUMMER_ABOVE: 0.0,  # Everything above 0°C is "summer"
            },
        }
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = "weather.home"
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response(
                "weather.home",
                [{"temperature": 10.0}, {"temperature": 10.0}, {"temperature": 10.0}],
            )
        )

        manager = AutoModeSwitchingManager(mock_hass, config_summer_lock, mock_coordinator)

        result = await manager.async_evaluate()

        # Forecast median 10°C < 21 - 2 = 19 → suggests HEAT
        # Season is summer (10°C > summer_above=0) → HEAT is blocked
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_forecast_and_no_outdoor_temp(self, mock_hass, mock_coordinator, default_config):
        """Test returns None when neither forecast nor outdoor temp is available."""
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = None
        mock_coordinator.outdoor_temp = None

        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_evaluate()

        assert result is None

    @pytest.mark.asyncio
    async def test_falls_back_to_outdoor_temp_when_no_forecast(self, mock_hass, mock_coordinator, default_config):
        """Test falls back to coordinator.outdoor_temp when forecast is unavailable."""
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = None
        # Outdoor temp well below setpoint - threshold → should suggest HEAT
        mock_coordinator.outdoor_temp = 5.0

        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_evaluate()

        # 5.0 < 21.0 - 2.0 = 19.0 → HEAT
        assert result == HVACMode.HEAT

    @pytest.mark.asyncio
    async def test_returns_none_when_no_active_zones(self, mock_hass, mock_coordinator, default_config):
        """Test returns None when no active zones."""
        mock_coordinator.get_active_zone_setpoints.return_value = []

        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        result = await manager.async_evaluate()

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_mode_unchanged(self, mock_hass, mock_coordinator, default_config):
        """Test returns None when target mode equals current mode (already switched)."""
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

        # Coordinator records the switch (H06)
        manager.mark_switched(result1)

        # Allow second evaluation by bypassing the rate-limit
        manager._last_switch = 0.0

        # Second evaluation with same conditions — mode already HEAT, no change
        result2 = await manager.async_evaluate()
        assert result2 is None  # No change needed

    @pytest.mark.asyncio
    async def test_updates_state_on_switch(self, mock_hass, mock_coordinator, default_config):
        """Test mark_switched updates internal state after coordinator applies the switch.

        H06: async_evaluate no longer mutates _current_mode/_last_switch.
        Those are updated only by mark_switched().
        """
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

        # State unchanged until coordinator calls mark_switched (H06)
        assert manager.current_mode is None
        assert manager.last_switch_time == 0.0

        # Coordinator confirms zones were switched
        manager.mark_switched(result)

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
        """Test debug attributes include switch times after mark_switched (H06/H07)."""
        mock_coordinator.outdoor_temp = 15.0
        mock_coordinator.get_active_zone_setpoints.return_value = [21.0]
        mock_coordinator.weather_entity = "weather.home"
        mock_hass.states.get.return_value = MagicMock()
        mock_hass.services.async_call = AsyncMock(
            return_value=mock_forecast_response("weather.home", [{"temperature": 15.0}])
        )
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)

        # Before mark_switched, no switch times
        attrs = manager.get_state_attributes(debug=True)
        assert "last_switch" not in attrs.get("auto_mode_switching", {})

        # Evaluate then record the switch (H06: coordinator calls mark_switched)
        result = await manager.async_evaluate()
        manager.mark_switched(result)

        attrs = manager.get_state_attributes(debug=True)

        assert "last_switch" in attrs["auto_mode_switching"]
        assert "next_allowed_switch" in attrs["auto_mode_switching"]

    def test_mark_switched_does_not_recompute_iso_on_attribute_reads(self, mock_hass, mock_coordinator, default_config):
        """ISO strings pre-computed in mark_switched, not in get_state_attributes (H07)."""
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)
        mock_coordinator.get_active_zone_setpoints.return_value = [20.0]

        # Simulate a switch
        manager.mark_switched(HVACMode.HEAT)

        cached_last = manager._cached_last_switch_iso
        cached_next = manager._cached_next_allowed_switch_iso

        # Multiple attribute reads must return the same cached strings
        for _ in range(10):
            attrs = manager.get_state_attributes(debug=True)
            assert attrs["auto_mode_switching"]["last_switch"] == cached_last
            assert attrs["auto_mode_switching"]["next_allowed_switch"] == cached_next

    def test_should_switch_false_within_interval(self, mock_hass, mock_coordinator, default_config):
        """_should_switch returns False within the min_switch_interval (A03/H06)."""
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)
        manager.mark_switched(HVACMode.HEAT)

        assert manager._should_switch() is False

    def test_should_switch_true_when_never_switched(self, mock_hass, mock_coordinator, default_config):
        """_should_switch returns True on first evaluation (A03/H06)."""
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)
        assert manager._should_switch() is True

    def test_compute_target_mode_heat(self, mock_hass, mock_coordinator, default_config):
        """_compute_target_mode returns HEAT when forecast cold (A03)."""
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)
        # threshold=2.0: forecast 15 < setpoint 21 - 2 = 19
        result = manager._compute_target_mode(15.0, 21.0, "shoulder")
        assert result == HVACMode.HEAT

    def test_compute_target_mode_cool(self, mock_hass, mock_coordinator, default_config):
        """_compute_target_mode returns COOL when forecast warm (A03)."""
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)
        # threshold=2.0: forecast 25 > setpoint 21 + 2 = 23
        result = manager._compute_target_mode(25.0, 21.0, "shoulder")
        assert result == HVACMode.COOL

    def test_compute_target_mode_none_in_hysteresis(self, mock_hass, mock_coordinator, default_config):
        """_compute_target_mode returns None in hysteresis zone (A03)."""
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)
        # threshold=2.0: forecast 21 is within ±2 of setpoint 21
        result = manager._compute_target_mode(21.0, 21.0, "shoulder")
        assert result is None

    def test_compute_target_mode_winter_blocks_cool(self, mock_hass, mock_coordinator, default_config):
        """_compute_target_mode returns None when winter blocks COOL (A03)."""
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)
        # Without season lock, 25 > 21+2 → COOL
        result = manager._compute_target_mode(25.0, 21.0, "winter")
        assert result is None

    def test_compute_target_mode_no_change_when_already_in_mode(self, mock_hass, mock_coordinator, default_config):
        """_compute_target_mode returns None when current mode already matches (A03)."""
        manager = AutoModeSwitchingManager(mock_hass, default_config, mock_coordinator)
        manager.mark_switched(HVACMode.HEAT)  # set _current_mode = HEAT
        manager._last_switch = 0.0  # bypass rate limit for this test

        # Forecast still warrants HEAT, but current_mode is already HEAT
        result = manager._compute_target_mode(15.0, 21.0, "shoulder")
        assert result is None


class TestForecastHoursAlias:
    """M04: forecast_hours alias must not be shadowed by forecast_days schema default."""

    def test_schema_forecast_days_has_no_default(self):
        """M04: AUTO_MODE_SWITCHING_SCHEMA must NOT set a default on forecast_days.

        Bug: ``vol.Optional(CONF_FORECAST_DAYS, default=DEFAULT_FORECAST_DAYS)`` injects
        ``forecast_days=3`` even when the user only configured ``forecast_hours: 12``.
        The manager's ``config.get(CONF_FORECAST_DAYS) or config.get("forecast_hours")``
        then returns 3 (truthy) and the alias is silently ignored.

        Fix: remove ``default=`` from the key so ``forecast_days`` is absent from the
        validated dict when the user didn't explicitly set it.  The manager's ``or``
        chain then reaches ``forecast_hours`` correctly.

        This test inspects the schema key objects directly using duck-typing (not
        ``isinstance(key, vol.Optional)``), so it is immune to the
        ``homeassistant.helpers.config_validation`` AND voluptuous sys.modules mocking
        that test_sensor.py applies at module load time.
        """
        from custom_components.adaptive_climate import AUTO_MODE_SWITCHING_SCHEMA
        from custom_components.adaptive_climate.const import CONF_FORECAST_DAYS

        forecast_days_key = None
        for key in AUTO_MODE_SWITCHING_SCHEMA.schema:
            # Duck-type: real vol.Optional instances carry a .schema attribute
            # Do NOT use isinstance(key, vol.Optional) — vol.Optional is mocked by
            # test_sensor.py and isinstance() rejects non-type second arguments.
            if getattr(key, "schema", None) == CONF_FORECAST_DAYS:
                forecast_days_key = key
                break

        assert forecast_days_key is not None, (
            f"Could not find '{CONF_FORECAST_DAYS}' key in AUTO_MODE_SWITCHING_SCHEMA — did the schema change?"
        )
        # Real voluptuous UNDEFINED is a singleton sentinel (class name varies by version:
        # "_Undefined" or "Undefined").  Comparing against vol.UNDEFINED would fail after
        # test_sensor.py mocks voluptuous, so we check the type name instead — works
        # regardless of sys.modules state.
        default_type_name = type(forecast_days_key.default).__name__
        assert "undefined" in default_type_name.lower(), (
            f"M04: '{CONF_FORECAST_DAYS}' must have no default in AUTO_MODE_SWITCHING_SCHEMA, "
            f"got default={forecast_days_key.default!r} (type={default_type_name!r}). "
            "This default shadows the 'forecast_hours' backward-compat alias."
        )

    def test_manager_uses_forecast_hours_when_forecast_days_absent(self, mock_hass, mock_coordinator):
        """M04 regression: manager must read forecast_hours when forecast_days absent from config.

        This is the manager-level contract: after the schema fix the validated config
        will NOT contain ``forecast_days`` when the user only set ``forecast_hours``,
        so the manager's ``or``-chain must reach ``forecast_hours``.
        """
        # Simulate what the FIXED schema produces — no forecast_days injected
        config = {"forecast_hours": 12}
        manager = AutoModeSwitchingManager(mock_hass, config, mock_coordinator)

        assert manager._forecast_days == 12, (
            f"Expected _forecast_days=12 from forecast_hours, got {manager._forecast_days}. "
            "Manager's or-chain must reach forecast_hours when forecast_days is absent."
        )

    def test_manager_forecast_days_takes_precedence_over_alias(self, mock_hass, mock_coordinator):
        """M04 regression: explicit forecast_days wins when both keys present."""
        config = {"forecast_days": 5, "forecast_hours": 12}
        manager = AutoModeSwitchingManager(mock_hass, config, mock_coordinator)

        assert manager._forecast_days == 5, (
            f"Expected _forecast_days=5 (explicit key takes precedence), got {manager._forecast_days}."
        )

    def test_manager_default_when_neither_key_set(self, mock_hass, mock_coordinator):
        """M04 regression: DEFAULT_FORECAST_DAYS (3) applies when neither key is present."""
        from custom_components.adaptive_climate.const import DEFAULT_FORECAST_DAYS

        manager = AutoModeSwitchingManager(mock_hass, {}, mock_coordinator)

        assert manager._forecast_days == DEFAULT_FORECAST_DAYS, (
            f"Expected _forecast_days={DEFAULT_FORECAST_DAYS} (default), got {manager._forecast_days}. "
            "Default fallback must apply when no forecast key is configured."
        )
