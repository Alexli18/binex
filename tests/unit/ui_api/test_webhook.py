"""Unit tests for WebhookSender with retry logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from binex.webhook import WebhookSender


@pytest.fixture
def sender():
    return WebhookSender(url="https://example.com/hook")


class TestWebhookSenderInit:
    def test_creates_with_url(self):
        s = WebhookSender(url="https://example.com/hook")
        assert s.url == "https://example.com/hook"

    def test_from_config_with_url(self):
        s = WebhookSender.from_config(url="https://example.com/hook")
        assert s is not None
        assert s.url == "https://example.com/hook"

    def test_from_config_with_none_returns_none(self):
        s = WebhookSender.from_config(url=None)
        assert s is None

    def test_from_config_with_empty_string_returns_none(self):
        s = WebhookSender.from_config(url="")
        assert s is None


class TestWebhookSenderSend:
    @pytest.mark.asyncio
    async def test_successful_send(self, sender: WebhookSender):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            client = AsyncMock()
            client.post = AsyncMock(return_value=mock_response)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client

            result = await sender.send({"event": "run.completed", "run_id": "r1"})
            assert result is True
            client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_retries_on_failure(self, sender: WebhookSender):
        mock_response_fail = MagicMock()
        mock_response_fail.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "500", request=MagicMock(), response=mock_response_fail,
            ),
        )

        mock_response_ok = MagicMock()
        mock_response_ok.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient, \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            client = AsyncMock()
            client.post = AsyncMock(
                side_effect=[mock_response_fail, mock_response_ok],
            )
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client

            result = await sender.send({"event": "run.completed"})
            assert result is True
            assert client.post.call_count == 2
            mock_sleep.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_fails_after_max_retries(self, sender: WebhookSender):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "500", request=MagicMock(), response=mock_response,
            ),
        )

        with patch("httpx.AsyncClient") as MockClient, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            client = AsyncMock()
            client.post = AsyncMock(return_value=mock_response)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client

            result = await sender.send({"event": "run.failed"})
            assert result is False
            assert client.post.call_count == 3  # 3 attempts

    @pytest.mark.asyncio
    async def test_handles_connection_error(self, sender: WebhookSender):
        with patch("httpx.AsyncClient") as MockClient, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            client = AsyncMock()
            client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client

            result = await sender.send({"event": "run.failed"})
            assert result is False
            assert client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self, sender: WebhookSender):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "500", request=MagicMock(), response=mock_response,
            ),
        )

        with patch("httpx.AsyncClient") as MockClient, \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            client = AsyncMock()
            client.post = AsyncMock(return_value=mock_response)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client

            await sender.send({"event": "run.failed"})
            # backoff: 1s, 2s (after 1st and 2nd failure)
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(1)
            mock_sleep.assert_any_call(2)

    @pytest.mark.asyncio
    async def test_sends_json_payload(self, sender: WebhookSender):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:
            client = AsyncMock()
            client.post = AsyncMock(return_value=mock_response)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client

            payload = {"event": "run.completed", "run_id": "r1"}
            await sender.send(payload)

            call_kwargs = client.post.call_args
            assert call_kwargs[0][0] == "https://example.com/hook"
            assert call_kwargs[1]["json"] == payload
