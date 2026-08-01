"""Tests for water temperature state persistence in LearningDataStore."""

from __future__ import annotations

import copy
import json
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


@pytest.mark.asyncio
async def test_save_requires_a_hass_instance(store):
    store.hass = None

    with pytest.raises(RuntimeError, match="requires HomeAssistant instance"):
        await store.async_save_water_temp_state(SAMPLE_STATE)


@pytest.mark.asyncio
async def test_save_stores_a_deep_copy_not_a_live_reference(store):
    """A debounced zone-save serializes `self._data` later — mutating the
    caller's dict after save() returns must never affect what gets persisted.
    """
    mutable_state = copy.deepcopy(SAMPLE_STATE)

    await store.async_save_water_temp_state(mutable_state)
    mutable_state["cooling"]["ramp_start_value"] = 99.0
    mutable_state["last_written"]["number.hp_cool_supply"] = 1.0

    assert store._data["water_temp_state"] == SAMPLE_STATE


@pytest.mark.asyncio
async def test_load_returns_a_copy_not_the_live_internal_dict(store):
    """Mutating the dict returned by load() must never corrupt internal state.

    Saves an isolated deep copy of SAMPLE_STATE (never the shared module-level
    object itself) so that, pre-fix, mutating `loaded` cannot leak into the
    SAMPLE_STATE constant and mask the bug via a trivially-true self-reference
    comparison.
    """
    await store.async_save_water_temp_state(copy.deepcopy(SAMPLE_STATE))

    loaded = await store.async_load_water_temp_state()
    loaded["cooling"]["ramp_start_value"] = 999.0
    loaded["last_written"]["number.hp_cool_supply"] = 1.0

    assert store._data["water_temp_state"] == SAMPLE_STATE
    assert await store.async_load_water_temp_state() == SAMPLE_STATE


@pytest.mark.asyncio
async def test_saved_state_round_trips_through_json(store):
    """Spec mandates ISO strings only — a stray datetime object leaking into
    the state must fail this fast (json.dumps raises on non-serializable types).
    """
    await store.async_save_water_temp_state(SAMPLE_STATE)

    saved = store._store.async_save.await_args.args[0]
    assert json.loads(json.dumps(saved["water_temp_state"])) == SAMPLE_STATE
