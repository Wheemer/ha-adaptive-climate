"""Tests for the pure Magnus-Tetens dew point helper."""

from __future__ import annotations

import pytest

from custom_components.adaptive_climate.helpers.dew_point import (
    MAGNUS_B,
    MAGNUS_C,
    dew_point,
)


def test_reference_point_25c_60pct():
    """25 degC / 60% RH -> 16.69 degC (spec reference point)."""
    assert dew_point(25.0, 60.0) == pytest.approx(16.69, abs=0.01)


def test_reference_point_20c_50pct():
    """20 degC / 50% RH -> 9.3 degC (spec reference point)."""
    assert dew_point(20.0, 50.0) == pytest.approx(9.3, abs=0.1)


def test_reference_point_30c_80pct():
    """30 degC / 80% RH -> 26.2 degC (spec reference point)."""
    assert dew_point(30.0, 80.0) == pytest.approx(26.2, abs=0.1)


def test_saturation_returns_air_temperature():
    """At 100% RH the dew point equals the air temperature."""
    assert dew_point(21.5, 100.0) == pytest.approx(21.5, abs=0.01)


def test_dew_point_is_monotonic_in_humidity():
    """Higher RH at fixed temperature always yields a higher dew point."""
    assert dew_point(24.0, 40.0) < dew_point(24.0, 55.0) < dew_point(24.0, 70.0)


def test_rh_zero_raises_value_error():
    """RH of 0 is outside the valid (0, 100] domain."""
    with pytest.raises(ValueError, match="Relative humidity"):
        dew_point(22.0, 0.0)


def test_rh_negative_raises_value_error():
    """Negative RH is outside the valid (0, 100] domain."""
    with pytest.raises(ValueError, match="Relative humidity"):
        dew_point(22.0, -5.0)


def test_rh_above_100_raises_value_error():
    """RH above 100 is outside the valid (0, 100] domain."""
    with pytest.raises(ValueError, match="Relative humidity"):
        dew_point(22.0, 101.0)


def test_magnus_coefficients_are_the_specified_ones():
    """The spec pins b=17.62 and c=243.12."""
    assert MAGNUS_B == 17.62
    assert MAGNUS_C == 243.12
