"""Blind-reading fallback for registered zones whose HVAC mode is unresolvable.

Split out of ``water_temp_controller.py`` to keep that module under the
project's 800-line ceiling.  Addresses review finding #8 / R4:
``coordinator.get_zones_in_mode`` silently drops a zone whose climate entity
currently has no state at all (not yet loaded, renamed, unavailable), so such
a zone never reaches :class:`~.water_temp_sources.DewPointScanner` even though
the entity could well be in COOL mode.  Its humidity would otherwise be
excluded from the scan entirely while other zones drive cooling.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .water_temp_sources import DewPointScan, DewPointScanner, SourceReading

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..coordinator import AdaptiveThermostatCoordinator


def merge_unresolvable_zone_readings(
    scan: DewPointScan | None,
    *,
    hass: HomeAssistant,
    coordinator: AdaptiveThermostatCoordinator,
    scanner: DewPointScanner | None,
    cool_hvac_state: str,
    now: datetime,
) -> DewPointScan | None:
    """Fold in a blind reading for every registered zone whose mode can't be resolved.

    Mirrors the scanner's own handling of a resolved-mode zone with no usable
    temperature (review finding #8): contribute a conservative blind reading
    instead of ignoring the zone's humidity signal outright.

    Args:
        scan: The scanner's own result (or None if no scanner).
        hass: Home Assistant instance, used to check entity resolvability.
        coordinator: Zone registry, used to enumerate registered zones.
        scanner: The controller's :class:`DewPointScanner`, or None.
        cool_hvac_state: The HVAC state string that means "cooling" (``"cool"``).
        now: Current wall-clock time, threaded through to reading construction.

    Returns:
        ``scan`` unchanged when no zone is unresolvable; otherwise a new
        :class:`DewPointScan` with the extra readings folded into the
        worst-source and blind calculations.
    """
    extra_readings = _unresolvable_cool_zone_readings(
        hass=hass, coordinator=coordinator, scanner=scanner, cool_hvac_state=cool_hvac_state, now=now
    )
    if not extra_readings:
        return scan

    combined = (list(scan.readings) if scan is not None else []) + extra_readings
    worst = max(combined, key=lambda reading: reading.dew_point_c)
    return DewPointScan(
        dew_point=worst.dew_point_c,
        worst_source=worst.key,
        blind=not any(reading.real for reading in combined),
        readings=tuple(combined),
    )


def _unresolvable_cool_zone_readings(
    *,
    hass: HomeAssistant,
    coordinator: AdaptiveThermostatCoordinator,
    scanner: DewPointScanner | None,
    cool_hvac_state: str,
    now: datetime,
) -> list[SourceReading]:
    """Return a blind reading per registered zone whose HVAC mode is unresolvable.

    Returns:
        A blind :class:`SourceReading` for each zone that has a
        ``climate_entity_id`` resolving to no state at all (as opposed to a
        state that simply isn't "cool") and a configured ``humidity_sensor``.
        Empty when every registered zone's mode is resolvable, or cooling has
        no scanner.
    """
    if scanner is None:
        return []

    resolved_zone_ids = set(coordinator.get_zones_in_mode(cool_hvac_state))
    readings: list[SourceReading] = []
    for zone_id, zone_data in coordinator.get_all_zones().items():
        if zone_id in resolved_zone_ids:
            continue  # mode already resolved -- the scanner already covers it

        climate_entity_id = zone_data.get("climate_entity_id")
        if not climate_entity_id or hass.states.get(climate_entity_id) is not None:
            # No climate entity at all, or the entity resolves fine (just not
            # "cool", e.g. heat/off) -- correctly excluded, not our concern.
            continue

        humidity_entity_id = zone_data.get("humidity_sensor")
        if not humidity_entity_id or zone_data.get("exclude_from_dew_point"):
            continue

        # Reuses the scanner's own blind-reading construction (pinned to
        # WATER_TEMP_BLIND_MIN_SUPPLY) so an unresolvable-mode zone is
        # handled identically to a resolved zone with no usable temperature.
        readings.append(scanner._blind_zone_reading(zone_id, humidity_entity_id, now))

    return readings
