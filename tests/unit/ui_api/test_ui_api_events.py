"""Tests for the SSE streaming endpoint (GET /runs/{run_id}/events).

Covers the generator loop: frame format, terminal-event close, unsubscribe
in finally, default event type, and the keepalive branch (via a patched
wait_for — the 30 s timeout is hardcoded).

The CancelledError branch (client disconnect) is a conscious testing
boundary: only a real transport can genuinely cancel the generator task.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from binex.ui.api.events import event_bus


async def _wait_for_subscriber(run_id: str, timeout: float = 2.0) -> None:
    """Poll until the streaming request has registered its queue on the bus."""
    async def poll() -> None:
        while not event_bus._subscribers.get(run_id):
            await asyncio.sleep(0.01)

    await asyncio.wait_for(poll(), timeout=timeout)


async def _collect_stream(client, run_id: str) -> tuple[int, str, list[str]]:
    """Open the SSE stream and read it to completion."""
    async with client.stream("GET", f"/api/v1/runs/{run_id}/events") as resp:
        lines = [line async for line in resp.aiter_lines()]
        return resp.status_code, resp.headers.get("content-type", ""), lines


@pytest.mark.asyncio
async def test_stream_delivers_frames_and_closes_on_terminal_event(client):
    run_id = "run-sse-1"
    task = asyncio.create_task(_collect_stream(client, run_id))
    await _wait_for_subscriber(run_id)

    await event_bus.publish(run_id, {"type": "node:completed", "node_id": "a"})
    await event_bus.publish(run_id, {"type": "run:completed", "status": "completed"})

    status, content_type, lines = await asyncio.wait_for(task, timeout=5)
    assert status == 200
    assert content_type.startswith("text/event-stream")
    assert "event: node:completed" in lines
    assert any(line.startswith("data: ") and '"node_id": "a"' in line for line in lines)
    # run:completed is the terminal event — the stream must have ended by itself
    assert "event: run:completed" in lines
    # finally-block unsubscribed the queue
    assert event_bus._subscribers.get(run_id) == []


@pytest.mark.asyncio
async def test_event_without_type_defaults_to_message(client):
    run_id = "run-sse-2"
    task = asyncio.create_task(_collect_stream(client, run_id))
    await _wait_for_subscriber(run_id)

    await event_bus.publish(run_id, {"payload": 42})
    await event_bus.publish(run_id, {"type": "run:cancelled"})

    _, _, lines = await asyncio.wait_for(task, timeout=5)
    assert "event: message" in lines
    # run:cancelled is also terminal
    assert "event: run:cancelled" in lines


class _TimeoutThenTerminalQueue:
    """First get() times out (as if 30 s passed), second returns a terminal event."""

    def __init__(self) -> None:
        self.calls = 0

    async def get(self) -> dict:
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError
        return {"type": "run:completed", "status": "completed"}


@pytest.mark.asyncio
async def test_timeout_yields_keepalive_comment(client):
    # A TimeoutError from inside wait_for's coroutine lands in the same
    # except-branch as a real 30 s timeout — no global asyncio patching.
    fake_queue = _TimeoutThenTerminalQueue()

    with patch.object(event_bus, "subscribe", return_value=fake_queue):
        _, _, lines = await asyncio.wait_for(
            _collect_stream(client, "run-sse-3"), timeout=5,
        )

    assert ": keepalive" in lines
    assert "event: run:completed" in lines
    assert fake_queue.calls == 2
