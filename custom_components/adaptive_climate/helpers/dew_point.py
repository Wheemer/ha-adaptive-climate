"""Pure dew-point math (Magnus-Tetens).

Stateless helper with no Home Assistant imports so it can be unit-tested and
reused anywhere.  Lives under ``helpers/`` rather than ``adaptive/`` because
``adaptive/`` is reserved for learning and physics state.
"""

from __future__ import annotations

import math

# Magnus-Tetens coefficients (Sonntag 1990 set, valid roughly 0-60 degC).
MAGNUS_B = 17.62
MAGNUS_C = 243.12


def dew_point(temp_c: float, rh_pct: float) -> float:
    """Return the dew point in degC for an air temperature and relative humidity.

    Args:
        temp_c: Air temperature in degrees Celsius.
        rh_pct: Relative humidity in percent, in the half-open range (0, 100].

    Returns:
        Dew point temperature in degrees Celsius.

    Raises:
        ValueError: If ``rh_pct`` is <= 0 or > 100.  Project rules forbid
            ``assert`` in production code, so this is an explicit raise.
    """
    if rh_pct <= 0.0 or rh_pct > 100.0:
        raise ValueError(f"Relative humidity must be in the range (0, 100], got {rh_pct}")

    gamma = math.log(rh_pct / 100.0) + (MAGNUS_B * temp_c) / (MAGNUS_C + temp_c)
    return (MAGNUS_C * gamma) / (MAGNUS_B - gamma)
