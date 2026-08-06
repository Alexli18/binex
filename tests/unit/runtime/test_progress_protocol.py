"""Progress protocol + heartbeat timeouts for long-running nodes (issue #78)."""

from __future__ import annotations

import asyncio
import json

import pytest

from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.runtime.orchestrator import Orchestrator
from binex.runtime.progress import (
    HeartbeatTimeoutError,
    ProgressReporter,
    run_with_heartbeat,
)
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _art(node="n") -> Artifact:
    return Artifact(id=f"a_{node}", run_id="r", type="r", content={},
                    lineage=Lineage(produced_by=node))


def _task() -> TaskNode:
    return TaskNode(id="t", run_id="r", node_id="n", agent="local://x")


# ── ProgressReporter ─────────────────────────────────────────────────────

def test_reporter_forwards_and_clamps():
    seen = []
    r = ProgressReporter(on_progress=lambda f, m: seen.append((f, m)))
    r.report(1.5, "over")   # clamped to 1.0
    r.report(-0.2, "under")  # clamped to 0.0
    assert seen == [(1.0, "over"), (0.0, "under")]


# ── heartbeat watchdog ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_heartbeat_survives_while_reporting():
    reporter = ProgressReporter()

    async def work():
        for _ in range(5):
            await asyncio.sleep(0.04)
            reporter.report(0.2)
        return "done"

    result = await run_with_heartbeat(
        asyncio.ensure_future(work()), reporter, heartbeat_timeout_s=0.15,
    )
    assert result == "done"


@pytest.mark.asyncio
async def test_heartbeat_kills_silent_node():
    reporter = ProgressReporter()

    async def work():
        await asyncio.sleep(2.0)  # silent, never reports
        return "done"

    with pytest.raises(HeartbeatTimeoutError):
        await run_with_heartbeat(
            asyncio.ensure_future(work()), reporter, heartbeat_timeout_s=0.1,
        )


# ── LocalPythonAdapter progress plumbing ─────────────────────────────────

@pytest.mark.asyncio
async def test_adapter_passes_progress_to_opted_in_handler():
    seen = []

    async def handler(task, inputs, report_progress):
        report_progress(0.5, "half")
        return [_art()]

    adapter = LocalPythonAdapter(handler)
    reporter = ProgressReporter(on_progress=lambda f, m: seen.append((f, m)))
    await adapter.execute(_task(), [], "trace", progress=reporter)
    assert seen == [(0.5, "half")]


@pytest.mark.asyncio
async def test_adapter_legacy_handler_unaffected():
    async def handler(task, inputs):  # no report_progress param
        return [_art()]

    adapter = LocalPythonAdapter(handler)
    result = await adapter.execute(
        _task(), [], "trace", progress=ProgressReporter(),
    )
    assert result.artifacts  # runs fine, ignores progress


# ── trace SDK ────────────────────────────────────────────────────────────

def test_trace_progress_event(capsys):
    from binex.trace import trace

    trace.progress(0.3, "transcribing 36/120 min")
    err = capsys.readouterr().err
    line = [ln for ln in err.splitlines() if ln.strip()][-1]
    event = json.loads(line)
    assert event["type"] == "progress"
    assert event["fraction"] == 0.3
    assert "transcribing" in event["message"]


# ── orchestrator integration ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_orchestrator_emits_node_progress():
    events: list[dict] = []

    async def handler(task, inputs, report_progress):
        report_progress(0.5, "working")
        return [Artifact(
            id=f"art_{task.run_id}", run_id=task.run_id, type="r", content={},
            lineage=Lineage(produced_by=task.node_id),
        )]

    orch = Orchestrator(
        artifact_store=InMemoryArtifactStore(),
        execution_store=InMemoryExecutionStore(),
        event_callback=lambda e: events.append(e),
    )
    orch.dispatcher.register_adapter("local://track", LocalPythonAdapter(handler))
    workflow = {
        "name": "wf",
        "nodes": {"n": {"agent": "local://track", "inputs": {}, "outputs": ["r"]}},
    }
    summary = await orch.run_workflow(workflow)

    assert summary.status == "completed"
    progress_events = [e for e in events if e["type"] == "node:progress"]
    assert progress_events and progress_events[0]["fraction"] == 0.5
    assert progress_events[0]["message"] == "working"


def test_nodespec_heartbeat_field():
    from binex.models.workflow import NodeSpec

    node = NodeSpec(agent="local://x", outputs=["r"], heartbeat_timeout_ms=5000)
    assert node.heartbeat_timeout_ms == 5000
