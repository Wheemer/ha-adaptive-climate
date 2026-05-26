"""Tests for KeManager — Protocol-based interface (D5 clean-up).

All tests use the KeManagerState Protocol exclusively.  The backward-compat
callback constructor has been removed; these tests document the protocol-based
contract going forward.
"""

from __future__ import annotations

import pytest
import time
from unittest.mock import AsyncMock, Mock
from homeassistant.components.climate import HVACMode

from custom_components.adaptive_climate.managers.ke_manager import KeManager
from custom_components.adaptive_climate.adaptive.ke_learning import KeLearner
from custom_components.adaptive_climate.const import PIDChangeReason, HeatingType
from custom_components.adaptive_climate.protocols import KeManagerState


# =============================================================================
# Mock KeManagerState
# =============================================================================


class MockKeManagerState:
    """Minimal, mutable mock of KeManagerState for unit tests.

    Only the properties actually defined in the trimmed KeManagerState
    protocol are implemented here (TemperatureState + PIDState + HVACState
    minus the dead entries removed by D5).
    """

    def __init__(self):
        # TemperatureState
        self._current_temperature: float | None = 20.0
        self._target_temperature: float | None = 21.0
        self._ext_temp_value: float | None = 5.0
        self._cold_tolerance_value: float = 0.3
        self._hot_tolerance_value: float = 0.3

        # PIDState
        self._kp_value: float = 1.0
        self._ki_value: float = 0.1
        self._kd_value: float = 10.0
        self._ke_value: float = 0.0
        self._control_output_value: float = 50.0
        self._pid_control_i_value: float = 15.0

        # HVACState
        self._hvac_mode_value: HVACMode = HVACMode.HEAT
        self._heating_type_value: HeatingType = HeatingType.RADIATOR

        # KeManagerState extras
        self.entity_id: str = "climate.test_zone"
        self._is_pid_converged: bool = False

    # -- TemperatureState --

    @property
    def current_temperature(self) -> float | None:
        return self._current_temperature

    @current_temperature.setter
    def current_temperature(self, value: float | None) -> None:
        self._current_temperature = value

    @property
    def target_temperature(self) -> float | None:
        return self._target_temperature

    @target_temperature.setter
    def target_temperature(self, value: float | None) -> None:
        self._target_temperature = value

    @property
    def _ext_temp(self) -> float | None:
        return self._ext_temp_value

    @_ext_temp.setter
    def _ext_temp(self, value: float | None) -> None:
        self._ext_temp_value = value

    @property
    def _cold_tolerance(self) -> float:
        return self._cold_tolerance_value

    @_cold_tolerance.setter
    def _cold_tolerance(self, value: float) -> None:
        self._cold_tolerance_value = value

    @property
    def _hot_tolerance(self) -> float:
        return self._hot_tolerance_value

    @_hot_tolerance.setter
    def _hot_tolerance(self, value: float) -> None:
        self._hot_tolerance_value = value

    # -- PIDState --

    @property
    def _kp(self) -> float:
        return self._kp_value

    @property
    def _ki(self) -> float:
        return self._ki_value

    @property
    def _kd(self) -> float:
        return self._kd_value

    @property
    def _ke(self) -> float:
        return self._ke_value

    @_ke.setter
    def _ke(self, value: float) -> None:
        self._ke_value = value

    @property
    def _control_output(self) -> float:
        return self._control_output_value

    @property
    def pid_control_i(self) -> float:
        return self._pid_control_i_value

    # -- HVACState --

    @property
    def _hvac_mode(self) -> HVACMode:
        return self._hvac_mode_value

    @_hvac_mode.setter
    def _hvac_mode(self, value: HVACMode) -> None:
        self._hvac_mode_value = value

    @property
    def heating_type(self) -> HeatingType:
        return self._heating_type_value

    # -- KeManagerState --

    def is_pid_converged_for_ke(self) -> bool:
        return self._is_pid_converged


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_state() -> MockKeManagerState:
    """Protocol-based state mock."""
    return MockKeManagerState()


@pytest.fixture
def mock_ke_learner() -> Mock:
    """KeLearner stub with sensible defaults."""
    learner = Mock(spec=KeLearner)
    learner.enabled = False
    learner.current_ke = 0.5
    learner.add_observation = Mock()
    learner.calculate_ke_adjustment = Mock(return_value=0.6)
    learner.apply_ke_adjustment = Mock()
    learner.get_observations_summary = Mock(
        return_value={"count": 10, "outdoor_temp_range": "5-15", "correlation": 0.8}
    )
    learner.enable = Mock()
    return learner


@pytest.fixture
def mock_gains_manager() -> Mock:
    manager = Mock()
    manager.set_gains = Mock()
    return manager


@pytest.fixture
def action_callbacks() -> dict:
    return {
        "async_control_heating": AsyncMock(),
        "async_write_ha_state": AsyncMock(),
    }


def make_manager(
    state: MockKeManagerState,
    ke_learner: Mock | None = None,
    gains_manager: Mock | None = None,
    callbacks: dict | None = None,
) -> KeManager:
    """Convenience factory for KeManager instances in tests."""
    cb = callbacks or {}
    return KeManager(
        state=state,
        ke_learner=ke_learner,
        gains_manager=gains_manager,
        async_control_heating=cb.get("async_control_heating"),
        async_write_ha_state=cb.get("async_write_ha_state"),
    )


# =============================================================================
# Protocol conformance
# =============================================================================


class TestProtocolConformance:
    """MockKeManagerState satisfies the KeManagerState Protocol."""

    def test_mock_satisfies_protocol(self, mock_state):
        """isinstance check passes when all protocol members are implemented."""
        assert isinstance(mock_state, KeManagerState)

    def test_manager_initialises_with_protocol_state(
        self, mock_state, mock_ke_learner, mock_gains_manager, action_callbacks
    ):
        manager = make_manager(mock_state, mock_ke_learner, mock_gains_manager, action_callbacks)
        assert manager.ke_learner is mock_ke_learner
        assert manager.steady_state_start is None
        assert manager.last_ke_observation_time is None

    def test_manager_initialises_without_optional_args(self, mock_state):
        """state is the only required argument."""
        manager = KeManager(state=mock_state)
        assert manager.ke_learner is None
        assert manager._gains_manager is None


# =============================================================================
# Steady-state detection
# =============================================================================


class TestKeManagerSteadyState:
    """is_at_steady_state() logic."""

    @pytest.fixture
    def manager(self, mock_state, mock_ke_learner) -> KeManager:
        return make_manager(mock_state, mock_ke_learner)

    def test_not_steady_when_hvac_off(self, manager, mock_state):
        mock_state._hvac_mode = HVACMode.OFF
        assert manager.is_at_steady_state() is False
        assert manager.steady_state_start is None

    def test_not_steady_when_temp_none(self, manager, mock_state):
        mock_state.current_temperature = None
        assert manager.is_at_steady_state() is False
        assert manager.steady_state_start is None

    def test_not_steady_when_outside_tolerance(self, manager, mock_state):
        mock_state.current_temperature = 18.0  # 3 °C below target
        mock_state.target_temperature = 21.0
        assert manager.is_at_steady_state() is False
        assert manager.steady_state_start is None

    def test_steady_state_tracking_starts_within_tolerance(self, manager, mock_state):
        mock_state.current_temperature = 20.8  # within 0.3 °C
        mock_state.target_temperature = 21.0
        result = manager.is_at_steady_state()
        assert manager.steady_state_start is not None
        assert result is False  # Duration not yet reached

    def test_steady_state_achieved_after_duration(self, manager, mock_state):
        from custom_components.adaptive_climate import const

        mock_state.current_temperature = 20.8
        mock_state.target_temperature = 21.0

        # Kick off tracking
        manager.is_at_steady_state()

        # Simulate duration elapsed
        required = const.KE_STEADY_STATE_DURATION * 60
        manager._steady_state_start = time.monotonic() - required - 1

        assert manager.is_at_steady_state() is True

    def test_steady_state_resets_when_temp_leaves_tolerance(self, manager, mock_state):
        mock_state.current_temperature = 20.8
        mock_state.target_temperature = 21.0
        manager.is_at_steady_state()
        assert manager.steady_state_start is not None

        mock_state.current_temperature = 18.0
        manager.is_at_steady_state()
        assert manager.steady_state_start is None

    def test_tolerance_uses_maximum_of_cold_and_hot(self, manager, mock_state):
        mock_state._cold_tolerance = 0.5
        mock_state._hot_tolerance = 0.2
        # 0.6 °C below target: outside max(0.5, 0.2) = 0.5
        mock_state.current_temperature = 20.4
        mock_state.target_temperature = 21.0
        assert manager.is_at_steady_state() is False

        # 0.4 °C below target: inside 0.5 °C band
        mock_state.current_temperature = 20.6
        manager.is_at_steady_state()
        assert manager.steady_state_start is not None


# =============================================================================
# Ke observation recording
# =============================================================================


class TestKeManagerObservationRecording:
    """maybe_record_observation() logic."""

    @pytest.fixture
    def manager_converged(self, mock_state, mock_ke_learner, mock_gains_manager, action_callbacks) -> KeManager:
        """Manager whose state reports PID already converged."""
        mock_state._is_pid_converged = True
        return make_manager(mock_state, mock_ke_learner, mock_gains_manager, action_callbacks)

    def test_no_observation_when_learner_disabled_and_not_converged(
        self, mock_state, mock_ke_learner, action_callbacks
    ):
        mock_state._is_pid_converged = False
        manager = make_manager(mock_state, mock_ke_learner, callbacks=action_callbacks)
        mock_ke_learner.enabled = False

        manager.maybe_record_observation()

        mock_ke_learner.enable.assert_not_called()
        mock_ke_learner.add_observation.assert_not_called()

    def test_no_observation_when_no_ke_learner(self, mock_state, action_callbacks):
        manager = make_manager(mock_state, ke_learner=None, callbacks=action_callbacks)
        # Should return early without error
        manager.maybe_record_observation()

    def test_learner_enabled_when_pid_converges(self, manager_converged, mock_ke_learner, mock_gains_manager):
        mock_ke_learner.enabled = False
        mock_ke_learner.current_ke = 0.5

        manager_converged.maybe_record_observation()

        mock_ke_learner.enable.assert_called_once()
        mock_gains_manager.set_gains.assert_called_once_with(PIDChangeReason.KE_PHYSICS, ke=0.5)

    def test_observation_recorded_at_steady_state(self, manager_converged, mock_state, mock_ke_learner):
        from custom_components.adaptive_climate import const

        mock_ke_learner.enabled = True
        mock_state.current_temperature = 20.8
        mock_state.target_temperature = 21.0
        mock_state._ext_temp = 5.0

        # Reach steady state
        manager_converged.is_at_steady_state()
        required = const.KE_STEADY_STATE_DURATION * 60
        manager_converged._steady_state_start = time.monotonic() - required - 1

        manager_converged.maybe_record_observation()

        mock_ke_learner.add_observation.assert_called_once_with(
            outdoor_temp=5.0,
            pid_output=50.0,
            indoor_temp=20.8,
            target_temp=21.0,
        )
        assert manager_converged.last_ke_observation_time is not None

    def test_observation_rate_limited_to_5_minutes(self, manager_converged, mock_state, mock_ke_learner):
        from custom_components.adaptive_climate import const

        mock_ke_learner.enabled = True
        mock_state.current_temperature = 20.8
        mock_state.target_temperature = 21.0

        manager_converged.is_at_steady_state()
        required = const.KE_STEADY_STATE_DURATION * 60
        manager_converged._steady_state_start = time.monotonic() - required - 1

        manager_converged.maybe_record_observation()
        assert mock_ke_learner.add_observation.call_count == 1

        # Immediate retry — should be skipped
        manager_converged.maybe_record_observation()
        assert mock_ke_learner.add_observation.call_count == 1

        # Simulate 5+ minutes passing
        manager_converged._last_ke_observation_time = time.monotonic() - 301
        manager_converged.maybe_record_observation()
        assert mock_ke_learner.add_observation.call_count == 2

    def test_no_observation_when_outdoor_temp_unavailable(self, manager_converged, mock_state, mock_ke_learner):
        from custom_components.adaptive_climate import const

        mock_ke_learner.enabled = True
        mock_state._ext_temp = None
        mock_state.current_temperature = 20.8
        mock_state.target_temperature = 21.0

        manager_converged.is_at_steady_state()
        required = const.KE_STEADY_STATE_DURATION * 60
        manager_converged._steady_state_start = time.monotonic() - required - 1

        manager_converged.maybe_record_observation()
        mock_ke_learner.add_observation.assert_not_called()

    def test_no_physics_ke_applied_when_gains_manager_absent(self, mock_state, mock_ke_learner):
        """When gains_manager is None the Ke enable still works, just no history."""
        mock_state._is_pid_converged = True
        mock_ke_learner.enabled = False
        mock_ke_learner.current_ke = 0.5

        manager = make_manager(mock_state, mock_ke_learner, gains_manager=None)
        manager.maybe_record_observation()

        # Learner still enabled even without gains_manager
        mock_ke_learner.enable.assert_called_once()


# =============================================================================
# Adaptive Ke application
# =============================================================================


class TestKeManagerAdaptiveApplication:
    """async_apply_adaptive_ke() logic."""

    @pytest.fixture
    def manager(self, mock_state, mock_ke_learner, mock_gains_manager, action_callbacks) -> KeManager:
        return make_manager(mock_state, mock_ke_learner, mock_gains_manager, action_callbacks)

    @pytest.mark.asyncio
    async def test_apply_adaptive_ke_success(
        self, manager, mock_ke_learner, mock_gains_manager, action_callbacks, mock_state
    ):
        mock_ke_learner.enabled = True
        mock_ke_learner.calculate_ke_adjustment.return_value = 0.6
        mock_state._ke = 0.4

        await manager.async_apply_adaptive_ke()

        mock_ke_learner.apply_ke_adjustment.assert_called_once_with(0.6)
        mock_gains_manager.set_gains.assert_called_once_with(PIDChangeReason.KE_LEARNING, ke=0.6)
        action_callbacks["async_control_heating"].assert_called_once_with(calc_pid=True)
        action_callbacks["async_write_ha_state"].assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_adaptive_ke_no_learner(self, manager, action_callbacks):
        manager._ke_learner = None
        await manager.async_apply_adaptive_ke()
        action_callbacks["async_control_heating"].assert_not_called()
        action_callbacks["async_write_ha_state"].assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_adaptive_ke_learner_disabled(self, manager, mock_ke_learner, action_callbacks):
        mock_ke_learner.enabled = False
        await manager.async_apply_adaptive_ke()
        mock_ke_learner.apply_ke_adjustment.assert_not_called()
        action_callbacks["async_control_heating"].assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_adaptive_ke_insufficient_data(self, manager, mock_ke_learner, action_callbacks):
        mock_ke_learner.enabled = True
        mock_ke_learner.calculate_ke_adjustment.return_value = None
        await manager.async_apply_adaptive_ke()
        mock_ke_learner.apply_ke_adjustment.assert_not_called()
        action_callbacks["async_control_heating"].assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_adaptive_ke_without_gains_manager(self, mock_state, mock_ke_learner, action_callbacks):
        """Without a gains_manager, Ke is still applied to the learner."""
        mock_ke_learner.enabled = True
        mock_ke_learner.calculate_ke_adjustment.return_value = 0.7
        mock_state._ke = 0.3

        manager = make_manager(mock_state, mock_ke_learner, gains_manager=None, callbacks=action_callbacks)
        await manager.async_apply_adaptive_ke()

        # Learner still gets the adjustment
        mock_ke_learner.apply_ke_adjustment.assert_called_once_with(0.7)
        # Callbacks still fire
        action_callbacks["async_control_heating"].assert_called_once_with(calc_pid=True)
        action_callbacks["async_write_ha_state"].assert_called_once()


# =============================================================================
# State restoration
# =============================================================================


class TestKeManagerStateRestoration:
    """restore_state() always resets monotonic timestamps."""

    @pytest.fixture
    def manager(self, mock_state, mock_ke_learner) -> KeManager:
        return make_manager(mock_state, mock_ke_learner)

    def test_restore_resets_all_timestamps(self, manager):
        steady = time.monotonic() - 100
        obs = time.monotonic() - 50
        manager.restore_state(steady_state_start=steady, last_ke_observation_time=obs)
        assert manager.steady_state_start is None
        assert manager.last_ke_observation_time is None

    def test_restore_resets_with_partial_args(self, manager):
        manager.restore_state(steady_state_start=time.monotonic() - 100)
        assert manager.steady_state_start is None
        assert manager.last_ke_observation_time is None

    def test_restore_resets_with_none_args(self, manager):
        manager.restore_state(steady_state_start=None, last_ke_observation_time=None)
        assert manager.steady_state_start is None
        assert manager.last_ke_observation_time is None


# =============================================================================
# Properties and utilities
# =============================================================================


class TestKeManagerPropertiesAndUtilities:
    """ke_learner property and update_ke_learner()."""

    @pytest.fixture
    def manager(self, mock_state, mock_ke_learner) -> KeManager:
        return make_manager(mock_state, mock_ke_learner)

    def test_ke_learner_property(self, manager, mock_ke_learner):
        assert manager.ke_learner is mock_ke_learner

    def test_update_ke_learner(self, manager):
        new_learner = Mock(spec=KeLearner)
        manager.update_ke_learner(new_learner)
        assert manager.ke_learner is new_learner

    def test_update_ke_learner_to_none(self, manager):
        manager.update_ke_learner(None)
        assert manager.ke_learner is None
