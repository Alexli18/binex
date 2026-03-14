"""Tests for the EventBus and SSE events."""

from __future__ import annotations

import asyncio

import pytest

from binex.ui.api.events import EventBus


@pytest.mark.asyncio
async def test_subscribe_publish():
    """Subscribe to a run, publish an event, verify received."""
    bus = EventBus()
    queue = bus.subscribe("run-1")

    event = {"type": "node:started", "node_id": "A", "timestamp": "2026-01-01T00:00:00Z"}
    await bus.publish("run-1", event)

    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received == event
    assert received["type"] == "node:started"
    assert received["node_id"] == "A"


@pytest.mark.asyncio
async def test_fan_out():
    """Multiple subscribers get the same event."""
    bus = EventBus()
    q1 = bus.subscribe("run-1")
    q2 = bus.subscribe("run-1")

    event = {"type": "node:completed", "node_id": "B", "timestamp": "2026-01-01T00:00:01Z"}
    await bus.publish("run-1", event)

    r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    r2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert r1 == event
    assert r2 == event


@pytest.mark.asyncio
async def test_unsubscribe():
    """After unsubscribe, no more events are received."""
    bus = EventBus()
    queue = bus.subscribe("run-1")

    # Publish one event, then unsubscribe
    await bus.publish("run-1", {"type": "node:started", "node_id": "A", "timestamp": "t1"})
    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received["type"] == "node:started"

    bus.unsubscribe("run-1", queue)

    # Publish another event — queue should NOT receive it
    await bus.publish("run-1", {"type": "node:completed", "node_id": "A", "timestamp": "t2"})

    assert queue.empty(), "Queue should be empty after unsubscribe"


@pytest.mark.asyncio
async def test_publish_no_subscribers():
    """Publishing to a run with no subscribers does not raise."""
    bus = EventBus()
    # Should not raise
    await bus.publish("nonexistent", {"type": "node:started", "node_id": "X", "timestamp": "t"})


@pytest.mark.asyncio
async def test_separate_runs():
    """Subscribers only receive events for their own run."""
    bus = EventBus()
    q1 = bus.subscribe("run-1")
    q2 = bus.subscribe("run-2")

    await bus.publish("run-1", {"type": "node:started", "node_id": "A", "timestamp": "t1"})

    r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    assert r1["node_id"] == "A"
    assert q2.empty(), "run-2 subscriber should not receive run-1 events"
