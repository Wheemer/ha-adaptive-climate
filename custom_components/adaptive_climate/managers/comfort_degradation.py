"""Comfort degradation detection with rolling average."""

from __future__ import annotations

import logging
from collections import deque

_LOGGER = logging.getLogger(__name__)

COMFORT_DEGRADATION_THRESHOLD = 65
COMFORT_DROP_THRESHOLD = 15
MIN_SAMPLES_FOR_DETECTION = 12


def _pluralize(n: int, word: str, plural: str | None = None) -> str:
    """Return ``word`` or its plural form based on *n*.

    Args:
        n: Count value
        word: Singular form
        plural: Plural form; defaults to ``word + 's'``
    """
    if n == 1:
        return word
    return plural if plural is not None else f"{word}s"


class ComfortDegradationDetector:
    """Detects significant comfort score degradation.

    Tracks a 24h rolling average (288 samples at 5-min intervals).
    Fires when score < absolute threshold OR drops >15 from average.
    """

    def __init__(
        self,
        zone_id: str,
        zone_name: str,
        max_samples: int = 288,
    ) -> None:
        self._zone_id = zone_id
        self._zone_name = zone_name
        self._samples: deque[float] = deque(maxlen=max_samples)

    def record_score(self, score: float) -> None:
        """Record a comfort score sample."""
        self._samples.append(score)

    @property
    def rolling_average(self) -> float | None:
        """Get rolling average, or None if insufficient data."""
        if len(self._samples) < MIN_SAMPLES_FOR_DETECTION:
            return None
        return sum(self._samples) / len(self._samples)

    def check_degradation(self, current_score: float) -> bool:
        """Check if current score indicates degradation.

        Returns True if degradation detected.
        """
        avg = self.rolling_average
        if avg is None:
            return False

        if current_score < COMFORT_DEGRADATION_THRESHOLD:
            return True

        return avg - current_score >= COMFORT_DROP_THRESHOLD

    def build_context(
        self,
        contact_pauses: int = 0,
        humidity_pauses: int = 0,
    ) -> str:
        """Build cause attribution string.

        Returns empty string if no known causes.
        """
        causes = []
        if contact_pauses > 0:
            causes.append(f"{contact_pauses} contact sensor {_pluralize(contact_pauses, 'pause')}")
        if humidity_pauses > 0:
            causes.append(f"{humidity_pauses} humidity {_pluralize(humidity_pauses, 'pause')}")
        return " · ".join(causes)
