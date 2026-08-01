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
