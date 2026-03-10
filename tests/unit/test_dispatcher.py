"""Tests for task dispatcher."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import RetryPolicy, TaskNode, TaskStatus
from binex.runtime.dispatcher import Dispatcher


def _make_task(**kwargs) -> TaskNode:
    defaults = {
        "id": "task-1",
        "run_id": "run-1",
        "node_id": "node-1",
        "agent": "local://echo",
        "retry_policy": RetryPolicy(max_retries=1),
        "deadline_ms": 5000,
    }
    defaults.update(kwargs)
    return TaskNode(**defaults)


def _make_artifact(id: str = "art-1") -> Artifact:
    return Artifact(
        id=id, run_id="run-1", type="text", content="data",
        lineage=Lineage(produced_by="node-0"),
    )


@pytest.mark.asyncio
async def test_dispatch_success() -> None:
    output = [_make_artifact("out-1")]

    async def handler(task, inputs):
        return output

    adapter = LocalPythonAdapter(handler=handler)
    dispatcher = Dispatcher()
    dispatcher.register_adapter("local://echo", adapter)

    task = _make_task()
    result = await dispatcher.dispatch(task, [_make_artifact()], "trace-1")
    assert result.artifacts == output


@pytest.mark.asyncio
async def test_dispatch_retry_on_failure() -> None:
    call_count = 0

    async def handler(task, inputs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RuntimeError("transient error")
        return [_make_artifact("out-1")]

    adapter = LocalPythonAdapter(handler=handler)
    dispatcher = Dispatcher()
    dispatcher.register_adapter("local://echo", adapter)

    task = _make_task(retry_policy=RetryPolicy(max_retries=2, backoff="fixed"))
    result = await dispatcher.dispatch(task, [], "trace-1")
    assert len(result.artifacts) == 1
    assert call_count == 2


@pytest.mark.asyncio
async def test_dispatch_exhausts_retries() -> None:
    async def handler(task, inputs):
        raise RuntimeError("permanent error")

    adapter = LocalPythonAdapter(handler=handler)
    dispatcher = Dispatcher()
    dispatcher.register_adapter("local://echo", adapter)

    task = _make_task(retry_policy=RetryPolicy(max_retries=2, backoff="fixed"))
    with pytest.raises(RuntimeError, match="permanent error"):
        await dispatcher.dispatch(task, [], "trace-1")


@pytest.mark.asyncio
async def test_dispatch_timeout() -> None:
    import asyncio

    async def slow_handler(task, inputs):
        await asyncio.sleep(10)
        return []

    adapter = LocalPythonAdapter(handler=slow_handler)
    dispatcher = Dispatcher()
    dispatcher.register_adapter("local://echo", adapter)

    task = _make_task(deadline_ms=100)
    with pytest.raises(asyncio.TimeoutError):
        await dispatcher.dispatch(task, [], "trace-1")


@pytest.mark.asyncio
async def test_dispatch_unknown_adapter() -> None:
    dispatcher = Dispatcher()
    task = _make_task(agent="unknown://agent")
    with pytest.raises(KeyError, match="unknown://agent"):
        await dispatcher.dispatch(task, [], "trace-1")
