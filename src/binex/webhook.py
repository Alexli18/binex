"""WebhookSender — async HTTP POST with retry and exponential backoff."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_DELAYS = [1, 2, 4]  # seconds
_TIMEOUT = 10  # seconds


class WebhookSender:
    """Sends webhook payloads with retry logic."""

    def __init__(self, url: str) -> None:
        self.url = url

    @classmethod
    def from_config(cls, *, url: str | None) -> WebhookSender | None:
        """Factory: return a sender if url is provided, else None."""
        if not url:
            return None
        return cls(url=url)

    async def send(self, payload: dict[str, Any]) -> bool:
        """POST payload to webhook URL with retries. Returns True on success."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            for attempt in range(_MAX_RETRIES):
                try:
                    response = await client.post(self.url, json=payload)
                    response.raise_for_status()
                    return True
                except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as exc:
                    if attempt < _MAX_RETRIES - 1:
                        delay = _BACKOFF_DELAYS[attempt]
                        logger.warning(
                            "Webhook delivery failed (attempt %d/%d): %s. "
                            "Retrying in %ds...",
                            attempt + 1, _MAX_RETRIES, exc, delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.warning(
                            "Webhook delivery failed after %d attempts: %s",
                            _MAX_RETRIES, exc,
                        )
        return False
