"""NaN/Inf safety tests for PID controller entry points.

Pins the validation added in H08, H09, H10 — ensures that poisoned float
values are rejected before they can corrupt state or propagate to HA storage.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import ClassVar

import pytest

# Make the component importable without a running HA instance
sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components" / "adaptive_climate"))

from pid_controller import PID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pid() -> PID:
    """Return a basic PID instance with sane defaults."""
    return PID(kp=1.0, ki=0.01, kd=5.0, out_min=0, out_max=100)


# ---------------------------------------------------------------------------
# H08 — set_pid_param validation
# ---------------------------------------------------------------------------


class TestSetPidParam:
    """set_pid_param must reject NaN, Inf and negative values."""

    def test_nan_kp_raises(self):
        pid = _make_pid()
        with pytest.raises(ValueError):
            pid.set_pid_param(kp=float("nan"))

    def test_nan_ki_raises(self):
        pid = _make_pid()
        with pytest.raises(ValueError):
            pid.set_pid_param(ki=float("nan"))

    def test_nan_kd_raises(self):
        pid = _make_pid()
        with pytest.raises(ValueError):
            pid.set_pid_param(kd=float("nan"))

    def test_nan_ke_raises(self):
        pid = _make_pid()
        with pytest.raises(ValueError):
            pid.set_pid_param(ke=float("nan"))

    def test_inf_kp_raises(self):
        pid = _make_pid()
        with pytest.raises(ValueError):
            pid.set_pid_param(kp=float("inf"))

    def test_neg_inf_ki_raises(self):
        pid = _make_pid()
        with pytest.raises(ValueError):
            pid.set_pid_param(ki=float("-inf"))

    def test_negative_kp_raises(self):
        pid = _make_pid()
        with pytest.raises(ValueError):
            pid.set_pid_param(kp=-5.0)

    def test_negative_ki_raises(self):
        pid = _make_pid()
        with pytest.raises(ValueError):
            pid.set_pid_param(ki=-0.001)

    def test_negative_kd_raises(self):
        pid = _make_pid()
        with pytest.raises(ValueError):
            pid.set_pid_param(kd=-10.0)

    def test_non_numeric_raises_type_error(self):
        pid = _make_pid()
        with pytest.raises(TypeError):
            pid.set_pid_param(kp="abc")  # type: ignore[arg-type]

    def test_zero_is_valid(self):
        """Zero gains are valid (disables that term)."""
        pid = _make_pid()
        pid.set_pid_param(kp=0.0, ki=0.0, kd=0.0, ke=0.0)
        assert pid._Kp == 0.0
        assert pid.ki == 0.0

    def test_valid_values_accepted(self):
        pid = _make_pid()
        pid.set_pid_param(kp=2.5, ki=0.05, kd=8.0, ke=0.3)
        assert pid._Kp == 2.5
        assert pid.ki == 0.05
        assert pid._Kd == 8.0

    def test_state_unchanged_on_invalid(self):
        """Gains must be unchanged when a ValueError is raised."""
        pid = _make_pid()
        orig_kp = pid._Kp
        with pytest.raises(ValueError):
            pid.set_pid_param(kp=float("nan"))
        assert pid._Kp == orig_kp


# ---------------------------------------------------------------------------
# H08 — set_feedforward validation
# ---------------------------------------------------------------------------


class TestSetFeedforward:
    """set_feedforward must reject NaN, Inf and negative values."""

    def test_nan_raises(self):
        pid = _make_pid()
        with pytest.raises(ValueError):
            pid.set_feedforward(float("nan"))

    def test_inf_raises(self):
        pid = _make_pid()
        with pytest.raises(ValueError):
            pid.set_feedforward(float("inf"))

    def test_negative_raises(self):
        pid = _make_pid()
        with pytest.raises(ValueError):
            pid.set_feedforward(-1.0)

    def test_non_numeric_raises_type_error(self):
        pid = _make_pid()
        with pytest.raises(TypeError):
            pid.set_feedforward("bad")  # type: ignore[arg-type]

    def test_zero_is_valid(self):
        pid = _make_pid()
        pid.set_feedforward(0.0)
        assert pid.feedforward == 0.0

    def test_positive_value_accepted(self):
        pid = _make_pid()
        pid.set_feedforward(25.0)
        assert pid.feedforward == 25.0


# ---------------------------------------------------------------------------
# H10 — decay_integral validation
# ---------------------------------------------------------------------------


class TestDecayIntegral:
    """decay_integral must reject NaN and clamp out-of-range factors."""

    def test_nan_raises(self):
        pid = _make_pid()
        pid.integral = 10.0
        with pytest.raises(ValueError):
            pid.decay_integral(float("nan"))

    def test_integral_unchanged_on_nan(self):
        pid = _make_pid()
        pid.integral = 10.0
        with pytest.raises(ValueError):
            pid.decay_integral(float("nan"))
        assert pid.integral == 10.0

    def test_negative_factor_clamped_to_zero(self):
        """Negative factor clamps to 0 → integral cleared."""
        pid = _make_pid()
        pid.integral = 5.0
        pid.decay_integral(-0.5)
        assert pid.integral == 0.0

    def test_factor_above_one_clamped(self):
        """Factor > 1 clamps to 1 → integral unchanged."""
        pid = _make_pid()
        pid.integral = 5.0
        pid.decay_integral(2.0)
        assert pid.integral == pytest.approx(5.0)

    def test_valid_factor_0_5(self):
        pid = _make_pid()
        pid.integral = 10.0
        pid.decay_integral(0.5)
        assert pid.integral == pytest.approx(5.0)

    def test_factor_zero_clears_integral(self):
        pid = _make_pid()
        pid.integral = 10.0
        pid.decay_integral(0.0)
        assert pid.integral == pytest.approx(0.0)

    def test_factor_one_preserves_integral(self):
        pid = _make_pid()
        pid.integral = 7.3
        pid.decay_integral(1.0)
        assert pid.integral == pytest.approx(7.3)

    def test_inf_factor_clamped(self):
        """Inf clamps to 1.0 → integral unchanged."""
        pid = _make_pid()
        pid.integral = 4.0
        pid.decay_integral(float("inf"))
        assert pid.integral == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# H10 — scale_integral validation
# ---------------------------------------------------------------------------


class TestScaleIntegral:
    """scale_integral must reject non-finite and non-positive factors."""

    def test_nan_raises(self):
        pid = _make_pid()
        pid.integral = 10.0
        with pytest.raises(ValueError):
            pid.scale_integral(float("nan"))

    def test_inf_raises(self):
        pid = _make_pid()
        pid.integral = 10.0
        with pytest.raises(ValueError):
            pid.scale_integral(float("inf"))

    def test_zero_raises(self):
        pid = _make_pid()
        with pytest.raises(ValueError):
            pid.scale_integral(0.0)

    def test_negative_raises(self):
        pid = _make_pid()
        with pytest.raises(ValueError):
            pid.scale_integral(-1.0)

    def test_integral_unchanged_on_error(self):
        pid = _make_pid()
        pid.integral = 5.0
        with pytest.raises(ValueError):
            pid.scale_integral(float("nan"))
        assert pid.integral == pytest.approx(5.0)

    def test_valid_scale_down(self):
        pid = _make_pid()
        pid.integral = 10.0
        pid.scale_integral(0.5)
        assert pid.integral == pytest.approx(5.0)

    def test_valid_scale_up(self):
        pid = _make_pid()
        pid.integral = 4.0
        pid.scale_integral(2.5)
        assert pid.integral == pytest.approx(10.0)

    def test_scale_one_is_noop(self):
        pid = _make_pid()
        pid.integral = 6.6
        pid.scale_integral(1.0)
        assert pid.integral == pytest.approx(6.6)


# ---------------------------------------------------------------------------
# Fuzz harness — random invalid inputs over N iterations
# ---------------------------------------------------------------------------


class TestFuzzInvalidInputs:
    """Fuzz-style: random invalid floats must never leave the PID in a NaN state."""

    INVALID_FLOATS: ClassVar[list[float]] = [float("nan"), float("inf"), float("-inf"), -1.0, -0.001, -999.0]
    INVALID_STRINGS: ClassVar[list] = ["", "abc", "1e999", None, [], {}]

    def _assert_pid_state_clean(self, pid: PID) -> None:
        """Assert no NaN values leaked into PID state."""
        assert math.isfinite(pid._Kp), f"_Kp is not finite: {pid._Kp}"
        assert math.isfinite(pid.ki), f"ki is not finite: {pid.ki}"
        assert math.isfinite(pid._Kd), f"_Kd is not finite: {pid._Kd}"
        assert math.isfinite(pid.integral), f"integral is not finite: {pid.integral}"

    def test_set_pid_param_fuzz(self):
        """100 random invalid inputs to set_pid_param must not corrupt state."""
        pid = _make_pid()
        seed_vals = self.INVALID_FLOATS + self.INVALID_STRINGS
        rng = random.Random(42)

        for _ in range(100):
            bad_val = rng.choice(seed_vals)
            param = rng.choice(["kp", "ki", "kd", "ke"])
            try:
                pid.set_pid_param(**{param: bad_val})
            except (TypeError, ValueError):
                pass  # Expected

        self._assert_pid_state_clean(pid)

    def test_decay_integral_fuzz(self):
        """100 random invalid factors to decay_integral must not corrupt state."""
        pid = _make_pid()
        pid.integral = 5.0
        seed_vals = self.INVALID_FLOATS + self.INVALID_STRINGS
        rng = random.Random(99)

        for _ in range(100):
            bad_val = rng.choice(seed_vals)
            try:
                pid.decay_integral(bad_val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                pass  # Expected

        self._assert_pid_state_clean(pid)

    def test_scale_integral_fuzz(self):
        """100 random invalid factors to scale_integral must not corrupt state."""
        pid = _make_pid()
        pid.integral = 5.0
        seed_vals = self.INVALID_FLOATS + self.INVALID_STRINGS
        rng = random.Random(7)

        for _ in range(100):
            bad_val = rng.choice(seed_vals)
            try:
                pid.scale_integral(bad_val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                pass  # Expected

        self._assert_pid_state_clean(pid)

    def test_set_feedforward_fuzz(self):
        """100 random invalid values to set_feedforward must not corrupt state."""
        pid = _make_pid()
        seed_vals = self.INVALID_FLOATS + self.INVALID_STRINGS
        rng = random.Random(13)

        for _ in range(100):
            bad_val = rng.choice(seed_vals)
            try:
                pid.set_feedforward(bad_val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                pass  # Expected

        self._assert_pid_state_clean(pid)
