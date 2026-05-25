"""Centralized notification dispatch with cooldowns."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class NotificationManager:
    """Centralized notification dispatch with cooldown support.

    Sends iOS (mobile_app) and persistent notifications.
    Supports per-notification-id cooldowns to prevent spam.
    """

    # Suppress service after this many consecutive failures to avoid log spam
    _MAX_CONSECUTIVE_FAILURES = 3

    def __init__(
        self,
        hass: HomeAssistant,
        notify_service: str | None,
        persistent_notification: bool,
    ) -> None:
        self._hass = hass
        self._notify_service = notify_service
        self._persistent = persistent_notification
        self._cooldowns: dict[str, float] = {}
        self._consecutive_failures: dict[str, int] = {}

        # Warn early if the user included the "notify." domain prefix — it will still work
        # (the code strips it) but it's easy to misconfigure and good to surface early.
        if notify_service and notify_service.startswith("notify."):
            _LOGGER.warning(
                "notify_service %r starts with 'notify.' — the domain prefix will be stripped "
                "automatically, but consider removing it from your config to avoid confusion",
                notify_service,
            )

    async def async_send(
        self,
        notification_id: str,
        title: str,
        ios_message: str,
        persistent_message: str | None = None,
        cooldown_hours: float = 0,
    ) -> bool:
        """Send iOS + optional persistent notification with cooldown.

        Args:
            notification_id: Unique ID for cooldown tracking and persistent notification
            title: Notification title
            ios_message: Short message for iOS notification
            persistent_message: Longer markdown message for persistent notification (falls back to ios_message)
            cooldown_hours: Minimum hours between sends for this notification_id (0 = no cooldown)

        Returns:
            True if sent, False if suppressed by cooldown
        """
        if cooldown_hours > 0 and not self._check_cooldown(notification_id, cooldown_hours):
            _LOGGER.debug("Notification %s suppressed by cooldown", notification_id)
            return False

        sent_any = False

        # Send iOS notification
        if self._notify_service:
            ios_key = f"ios:{self._notify_service}"
            ios_failures = self._consecutive_failures.get(ios_key, 0)
            if ios_failures >= self._MAX_CONSECUTIVE_FAILURES:
                _LOGGER.debug(
                    "iOS notification via %r suppressed after %d consecutive failures",
                    self._notify_service,
                    ios_failures,
                )
            else:
                try:
                    if "." in self._notify_service:
                        _, service_name = self._notify_service.split(".", 1)
                    else:
                        service_name = self._notify_service

                    await self._hass.services.async_call(
                        "notify",
                        service_name,
                        {"title": title, "message": ios_message},
                        blocking=True,
                    )
                    sent_any = True
                    self._consecutive_failures[ios_key] = 0
                except Exception:
                    count = ios_failures + 1
                    self._consecutive_failures[ios_key] = count
                    if count >= self._MAX_CONSECUTIVE_FAILURES:
                        _LOGGER.warning(
                            "iOS notification via %r has failed %d times in a row; "
                            "further attempts will be suppressed. Check your notify_service config.",
                            self._notify_service,
                            count,
                        )
                    else:
                        _LOGGER.exception("Failed to send iOS notification")

        # Send persistent notification
        if self._persistent:
            persistent_key = "persistent"
            persistent_failures = self._consecutive_failures.get(persistent_key, 0)
            if persistent_failures >= self._MAX_CONSECUTIVE_FAILURES:
                _LOGGER.debug("Persistent notification suppressed after %d consecutive failures", persistent_failures)
            else:
                try:
                    await self._hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "notification_id": notification_id,
                            "title": title,
                            "message": persistent_message or ios_message,
                        },
                        blocking=True,
                    )
                    sent_any = True
                    self._consecutive_failures[persistent_key] = 0
                except Exception:
                    count = persistent_failures + 1
                    self._consecutive_failures[persistent_key] = count
                    if count >= self._MAX_CONSECUTIVE_FAILURES:
                        _LOGGER.warning(
                            "Persistent notification has failed %d times in a row; "
                            "further attempts will be suppressed.",
                            count,
                        )
                    else:
                        _LOGGER.exception("Failed to send persistent notification")

        # Record cooldown
        if cooldown_hours > 0 and sent_any:
            self._cooldowns[notification_id] = time.monotonic()

        return sent_any

    def _check_cooldown(self, notification_id: str, cooldown_hours: float) -> bool:
        """Return True if notification is allowed (not in cooldown)."""
        last_sent = self._cooldowns.get(notification_id)
        if last_sent is None:
            return True
        elapsed = time.monotonic() - last_sent
        return elapsed >= cooldown_hours * 3600
