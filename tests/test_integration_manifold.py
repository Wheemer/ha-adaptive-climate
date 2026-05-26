"""Integration tests for manifold state persistence across startup.

M01: Manifold state not restored on normal startup.

Root cause: The restore attempt in __init__.py ran before LearningDataStore was
created in climate_setup.py, so learning_store was always None and restore was
silently skipped.

Fix: Remove the early restore in __init__.py; add restore in climate_setup.py
AFTER LearningDataStore is created.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.adaptive_climate.const import DOMAIN


class TestManifoldStateRestoredAfterLearningStoreCreation:
    """M01: Verify manifold state is restored when LearningDataStore is first created."""

    @pytest.mark.asyncio
    async def test_manifold_restored_when_store_created_first_time(self):
        """M01: manifold_registry.restore_state() must be called when LearningDataStore
        is created for the first time and manifold_registry already exists in hass.data.
        """
        from custom_components.adaptive_climate.climate_setup import async_setup_platform

        # Arrange: manifold_registry exists in hass.data but no learning_store yet
        mock_manifold_registry = MagicMock()
        mock_manifold_state = {"2nd Floor": "2024-01-15T10:00:00+00:00"}

        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock()
        mock_store.async_load_manifold_state = AsyncMock(return_value=mock_manifold_state)

        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "manifold_registry": mock_manifold_registry,
                # Note: NO "learning_store" key — simulates first platform setup
            }
        }
        hass.config.units.temperature_unit = "°C"

        mock_platform = MagicMock()
        config = {"name": "test_zone"}  # No heater/cooler → early return after store creation

        with (
            patch(
                "custom_components.adaptive_climate.climate_setup.LearningDataStore",
                return_value=mock_store,
            ),
            patch("custom_components.adaptive_climate.climate_setup.entity_platform") as mock_ep,
        ):
            mock_ep.current_platform.get.return_value = mock_platform
            await async_setup_platform(hass, config, MagicMock())

        # Assert: restore_state was called with the loaded manifold state
        mock_store.async_load_manifold_state.assert_called_once()
        mock_manifold_registry.restore_state.assert_called_once_with(mock_manifold_state)

    @pytest.mark.asyncio
    async def test_manifold_not_restored_when_store_already_exists(self):
        """M01: restore_state must NOT be called on subsequent platform setups
        (when learning_store already exists in hass.data).
        """
        from custom_components.adaptive_climate.climate_setup import async_setup_platform

        mock_manifold_registry = MagicMock()
        mock_existing_store = AsyncMock()
        mock_existing_store.async_load_manifold_state = AsyncMock(return_value={"2nd Floor": "warm"})

        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "manifold_registry": mock_manifold_registry,
                "learning_store": mock_existing_store,  # Already created
            }
        }
        hass.config.units.temperature_unit = "°C"

        config = {"name": "test_zone_2"}  # No heater → early return

        with patch("custom_components.adaptive_climate.climate_setup.entity_platform") as mock_ep:
            mock_ep.current_platform.get.return_value = MagicMock()
            await async_setup_platform(hass, config, MagicMock())

        # Assert: restore_state was NOT called (store was already present)
        mock_manifold_registry.restore_state.assert_not_called()
        mock_existing_store.async_load_manifold_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_manifold_not_restored_when_no_registry(self):
        """M01: no error when LearningDataStore is first created but no manifold_registry."""
        from custom_components.adaptive_climate.climate_setup import async_setup_platform

        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock()
        mock_store.async_load_manifold_state = AsyncMock(return_value=None)

        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                # No manifold_registry, no learning_store
            }
        }
        hass.config.units.temperature_unit = "°C"

        config = {"name": "test_zone_3"}  # No heater → early return

        with (
            patch(
                "custom_components.adaptive_climate.climate_setup.LearningDataStore",
                return_value=mock_store,
            ),
            patch("custom_components.adaptive_climate.climate_setup.entity_platform") as mock_ep,
        ):
            mock_ep.current_platform.get.return_value = MagicMock()
            # Should not raise
            await async_setup_platform(hass, config, MagicMock())

        # Assert: no manifold restore attempted (no registry)
        mock_store.async_load_manifold_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_manifold_not_restored_when_state_is_none(self):
        """M01: restore_state is NOT called when async_load_manifold_state returns None."""
        from custom_components.adaptive_climate.climate_setup import async_setup_platform

        mock_manifold_registry = MagicMock()
        mock_store = AsyncMock()
        mock_store.async_load = AsyncMock()
        mock_store.async_load_manifold_state = AsyncMock(return_value=None)  # No saved state

        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "manifold_registry": mock_manifold_registry,
                # No learning_store
            }
        }
        hass.config.units.temperature_unit = "°C"

        config = {"name": "test_zone_4"}  # No heater → early return

        with (
            patch(
                "custom_components.adaptive_climate.climate_setup.LearningDataStore",
                return_value=mock_store,
            ),
            patch("custom_components.adaptive_climate.climate_setup.entity_platform") as mock_ep,
        ):
            mock_ep.current_platform.get.return_value = MagicMock()
            await async_setup_platform(hass, config, MagicMock())

        # restore_state should NOT be called when there's no saved state
        mock_manifold_registry.restore_state.assert_not_called()

    def test_early_restore_in_init_never_fires(self):
        """M01: The old restore path in __init__.py always found learning_store=None
        because LearningDataStore is created later in climate_setup.py.
        Verify that __init__.py no longer attempts the early restore.
        """
        import inspect
        import custom_components.adaptive_climate as init_module

        source = inspect.getsource(init_module)
        # The old comment explained the race condition
        assert "LearningDataStore is created later in climate_setup.py" not in source, (
            "Old early-restore comment still present in __init__.py — the early restore was not removed"
        )
