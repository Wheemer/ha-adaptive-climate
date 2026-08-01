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

_LOGGER = logging.getLogger(__name__)


class WaterTempSupplySensor(SensorEntity):
    """Reports the current effective supply water temperature target."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the sensor.

        Args:
            hass: Home Assistant instance.
        """
        # Deferred import: this is the only consumer of EntityCategory in the
        # sensors package. Resolving it at instantiation time (rather than at
        # module import time) keeps `sensor.py`'s module-level import of this
        # file from requiring `homeassistant.helpers.entity` to be importable
        # in every test that merely collects `sensor.py` for unrelated sensors.
        from homeassistant.helpers.entity import EntityCategory

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
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return self._attr_unique_id

    @property
    def name(self) -> str:
        """Return the name of this entity."""
        return self._attr_name

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
        except Exception:  # broad: one bad sensor must not block the others
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

    @property
    def available(self) -> bool:
        """Return whether the sensor currently has a usable reading."""
        return self._attr_available
