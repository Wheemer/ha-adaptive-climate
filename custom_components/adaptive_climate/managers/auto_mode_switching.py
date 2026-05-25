"""Auto mode switching manager for house-wide HVAC mode control."""

from __future__ import annotations

import logging
import statistics
import time
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_AUTO_MODE_THRESHOLD,
    CONF_FORECAST_DAYS,
    CONF_MIN_SWITCH_INTERVAL,
    CONF_SEASON_THRESHOLDS,
    CONF_SUMMER_ABOVE,
    CONF_WINTER_BELOW,
    DEFAULT_AUTO_MODE_THRESHOLD,
    DEFAULT_FORECAST_DAYS,
    DEFAULT_MIN_SWITCH_INTERVAL,
    DEFAULT_SUMMER_ABOVE,
    DEFAULT_WINTER_BELOW,
)

if TYPE_CHECKING:
    from ..coordinator import AdaptiveThermostatCoordinator

_LOGGER = logging.getLogger(__name__)


class AutoModeSwitchingManager:
    """Manages automatic house-wide heat/cool mode switching."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict,
        coordinator: AdaptiveThermostatCoordinator,
    ) -> None:
        """Initialize the auto mode switching manager."""
        self._hass = hass
        self._coordinator = coordinator

        # Configuration
        self._threshold = config.get(CONF_AUTO_MODE_THRESHOLD, DEFAULT_AUTO_MODE_THRESHOLD)
        self._min_switch_interval = config.get(CONF_MIN_SWITCH_INTERVAL, DEFAULT_MIN_SWITCH_INTERVAL)
        # Accept both "forecast_days" (current) and "forecast_hours" (legacy alias).
        # forecast_days takes precedence when both are present.
        self._forecast_days = config.get(CONF_FORECAST_DAYS) or config.get("forecast_hours") or DEFAULT_FORECAST_DAYS

        season_config = config.get(CONF_SEASON_THRESHOLDS, {})
        self._winter_below = season_config.get(CONF_WINTER_BELOW, DEFAULT_WINTER_BELOW)
        self._summer_above = season_config.get(CONF_SUMMER_ABOVE, DEFAULT_SUMMER_ABOVE)

        # State
        self._current_mode: str | None = None
        self._last_switch: float = 0.0  # monotonic timestamp
        self._cached_season: str = "shoulder"
        self._cached_forecast_median: float | None = None
        # H07: Cached ISO strings for get_state_attributes — recomputed only in mark_switched
        self._cached_last_switch_iso: str | None = None
        self._cached_next_allowed_switch_iso: str | None = None

    @property
    def current_mode(self) -> str | None:
        """Return the current auto-switched mode."""
        return self._current_mode

    @property
    def last_switch_time(self) -> float:
        """Return monotonic timestamp of last switch."""
        return self._last_switch

    def get_median_setpoint(self) -> float | None:
        """Get median setpoint from all active zones.

        Returns:
            Median setpoint temperature, or None if no active zones.
        """
        setpoints = self._coordinator.get_active_zone_setpoints()
        if not setpoints:
            _LOGGER.debug("No active zones for median setpoint calculation")
            return None
        return statistics.median(setpoints)

    async def async_get_season(self) -> str:
        """Get current season based on forecast median temperature.

        Returns:
            Season string: "winter", "summer", or "shoulder"
            - winter: forecast median < winter_below threshold
            - summer: forecast median > summer_above threshold
            - shoulder: in between (both modes allowed)
        """
        forecast_median = await self._async_get_forecast_median()
        self._cached_forecast_median = forecast_median

        if forecast_median is None:
            _LOGGER.debug("No forecast available, assuming shoulder season")
            self._cached_season = "shoulder"
            return "shoulder"

        if forecast_median < self._winter_below:
            self._cached_season = "winter"
            return "winter"
        elif forecast_median > self._summer_above:
            self._cached_season = "summer"
            return "summer"
        else:
            self._cached_season = "shoulder"
            return "shoulder"

    async def _async_get_daily_forecast(self) -> list[dict] | None:
        """Fetch daily forecast using weather.get_forecasts service.

        Returns:
            List of forecast entries, or None if unavailable.
        """
        weather_entity = self._coordinator.weather_entity
        if not weather_entity:
            _LOGGER.debug("No weather entity configured for forecast")
            return None

        state = self._hass.states.get(weather_entity)
        if state is None:
            _LOGGER.warning("Weather entity %s not found", weather_entity)
            return None

        try:
            result = await self._hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": weather_entity, "type": "daily"},
                blocking=True,
                return_response=True,
            )
            if not result or weather_entity not in result:
                _LOGGER.debug("No forecast response from %s", weather_entity)
                return None
            forecast = result[weather_entity].get("forecast", [])
            if not forecast:
                _LOGGER.debug("Empty forecast from %s", weather_entity)
                return None
            return forecast
        except Exception as err:
            _LOGGER.warning("Failed to get forecast from %s: %s", weather_entity, err)
            return None

    async def _async_get_forecast_median(self) -> float | None:
        """Get median temperature from daily weather forecast.

        Uses weather.get_forecasts service with type "daily" and calculates
        median of high temperatures over the next 7 days.

        Returns:
            Median forecast temperature, or None if forecast unavailable.
        """
        forecast = await self._async_get_daily_forecast()
        if not forecast:
            return None

        temps = []
        for entry in forecast[: self._forecast_days]:
            temp = entry.get("temperature")
            if temp is not None:
                temps.append(temp)

        if not temps:
            _LOGGER.debug("No temperature data in forecast")
            return None

        return statistics.median(temps)

    # -------------------------------------------------------------------------
    # A03: Pure-compute helpers — each does exactly one thing
    # -------------------------------------------------------------------------

    def _should_switch(self) -> bool:
        """Return True if the min_switch_interval has elapsed since the last switch.

        Skips the check on the very first evaluation (``_last_switch == 0``).
        """
        if self._last_switch > 0:
            elapsed = time.monotonic() - self._last_switch
            if elapsed < self._min_switch_interval:
                _LOGGER.debug(
                    "Min switch interval not met (%.0fs < %ds)",
                    elapsed,
                    self._min_switch_interval,
                )
                return False
        return True

    def _compute_target_mode(
        self,
        forecast_median: float,
        median_setpoint: float,
        season: str,
    ) -> str | None:
        """Pure-compute: decide target HVAC mode from inputs.

        Args:
            forecast_median: Median forecast or current outdoor temperature.
            median_setpoint: Median setpoint across active zones.
            season: Current season ("winter", "summer", or "shoulder").

        Returns:
            HVACMode.HEAT, HVACMode.COOL, or None (no change needed).
        """
        if forecast_median < median_setpoint - self._threshold:
            target_mode: str = HVACMode.HEAT
            _LOGGER.debug(
                "Forecast %.1f°C < setpoint %.1f°C - %.1f°C, suggesting HEAT",
                forecast_median,
                median_setpoint,
                self._threshold,
            )
        elif forecast_median > median_setpoint + self._threshold:
            target_mode = HVACMode.COOL
            _LOGGER.debug(
                "Forecast %.1f°C > setpoint %.1f°C + %.1f°C, suggesting COOL",
                forecast_median,
                median_setpoint,
                self._threshold,
            )
        else:
            _LOGGER.debug(
                "Forecast %.1f°C in hysteresis zone (%.1f°C ± %.1f°C), keeping current mode",
                forecast_median,
                median_setpoint,
                self._threshold,
            )
            return None

        # Season locking
        if season == "winter" and target_mode == HVACMode.COOL:
            _LOGGER.debug("Season locking: winter prevents switching to COOL")
            return None
        if season == "summer" and target_mode == HVACMode.HEAT:
            _LOGGER.debug("Season locking: summer prevents switching to HEAT")
            return None

        # No change if already in this mode
        if target_mode == self._current_mode:
            return None

        return target_mode

    def mark_switched(self, mode: str) -> None:
        """Record that a mode switch was successfully applied to ≥1 zone.

        Updates the rate-limit timestamp, current mode, and cached ISO strings
        so ``get_state_attributes`` does not recompute them on every read (H07).

        Args:
            mode: The HVAC mode that was applied.
        """
        now = time.monotonic()
        self._current_mode = mode
        self._last_switch = now

        # H07: Pre-compute ISO strings; recompute only here, not in get_state_attributes
        last_switch_dt = dt_util.utcnow()
        next_allowed = last_switch_dt + timedelta(seconds=self._min_switch_interval)
        self._cached_last_switch_iso = last_switch_dt.isoformat()
        self._cached_next_allowed_switch_iso = next_allowed.isoformat()

    async def async_evaluate(self) -> str | None:
        """Evaluate and return new mode if a switch is needed.

        Logic (A03 split):
        1. ``_should_switch()`` — rate-limit check
        2. ``get_median_setpoint()`` — inputs from active zones
        3. ``async_get_season()`` — forecast-based season classification
        4. ``_compute_target_mode()`` — pure mode decision

        Intentionally does NOT call ``mark_switched``.  The coordinator calls
        ``mark_switched`` only after confirming ≥1 zone received the command
        (H06), so a no-op evaluation (all OFF, service errors) does not consume
        the rate-limit interval.

        Returns:
            HVACMode.HEAT or HVACMode.COOL if switch needed, None otherwise.
        """
        # 1. Rate-limit guard
        if not self._should_switch():
            return None

        # 2. Inputs
        median_setpoint = self.get_median_setpoint()
        if median_setpoint is None:
            _LOGGER.debug("No active zones, skipping evaluation")
            return None

        # 3. Season + forecast (also caches _cached_forecast_median)
        season = await self.async_get_season()
        forecast_median = self._cached_forecast_median
        if forecast_median is None:
            # Forecast unavailable — fall back to current outdoor temperature.
            # Season defaults to "shoulder" (no locking) when forecast is absent.
            outdoor_temp = self._coordinator.outdoor_temp
            if outdoor_temp is None:
                _LOGGER.debug("No forecast and no outdoor temp available, skipping evaluation")
                return None
            _LOGGER.debug("No forecast available, falling back to current outdoor temp %.1f°C", outdoor_temp)
            forecast_median = outdoor_temp

        # 4. Pure mode decision
        target_mode = self._compute_target_mode(forecast_median, median_setpoint, season)
        if target_mode is None:
            return None

        _LOGGER.info(
            "Auto mode switching: %s -> %s (forecast=%.1f°C, setpoint=%.1f°C, season=%s)",
            self._current_mode,
            target_mode,
            forecast_median,
            median_setpoint,
            season,
        )
        return target_mode

    def get_state_attributes(self, debug: bool = False) -> dict:
        """Get state attributes for this manager.

        Args:
            debug: If True, include detailed debug attributes.

        Returns:
            Dictionary of state attributes.
        """
        attrs: dict = {
            "auto_mode_switching_enabled": True,
        }

        if not debug:
            return attrs

        # Debug-only attributes (use cached values from last evaluation)
        attrs["auto_mode_switching"] = {
            "current_season": self._cached_season,
            "forecast_median_temp": self._cached_forecast_median,
            "median_setpoint": self.get_median_setpoint(),
        }

        # H07: Use cached ISO strings; recomputed in mark_switched, not here
        if self._last_switch > 0 and self._cached_last_switch_iso is not None:
            attrs["auto_mode_switching"]["last_switch"] = self._cached_last_switch_iso
            attrs["auto_mode_switching"]["next_allowed_switch"] = self._cached_next_allowed_switch_iso

        return attrs
