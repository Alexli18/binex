"""Integration: workspace-backed runs — snapshots, serialization, jail (#75)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _writer(filename: str, content: str):
    async def _handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
        root = task.config.get("_workspace_root")
        assert root is not None, "workspace root must be injected into task config"
        target = Path(root, filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return [Artifact(
            id=f"art_{task.node_id}", run_id=task.run_id, type="result",
            content="ok", lineage=Lineage(produced_by=task.node_id),
        )]
    return _handler


def _orch(**handlers) -> Orchestrator:
    orch = Orchestrator(
        artifact_store=InMemoryArtifactStore(),
        execution_store=InMemoryExecutionStore(),
    )
    for agent, handler in handlers.items():
        orch.dispatcher.register_adapter(agent, LocalPythonAdapter(handler=handler))
    return orch


@pytest.mark.asyncio
async def test_workspace_snapshots_per_write_node(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)  # workspaces land under tmp_path/.binex/workspaces
    orch = _orch(**{
        "local://coder": _writer("src/main.py", "print(1)"),
        "local://asset": _writer("assets/logo.txt", "LOGO"),
    })
    wf = {
        "name": "proj", "workspace": {"source": "empty"},
        "nodes": {
            "coder": {"agent": "local://coder", "outputs": ["o"], "workspace": "write"},
            "asset": {"agent": "local://asset", "outputs": ["o"],
                      "workspace": "write", "depends_on": ["coder"]},
        },
    }
    summary = await orch.run_workflow(wf)
    assert summary.status == "completed"

    ws = orch._workspace
    assert ws.files_changed("coder") == ["src/main.py"]
    assert ws.files_changed("asset") == ["assets/logo.txt"]
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=ws.root, capture_output=True, text=True,
    ).stdout
    assert "node: coder" in log and "node: asset" in log
    ws.cleanup()


@pytest.mark.asyncio
async def test_read_node_gets_no_snapshot(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    async def reader(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
        # A read node may inspect files but should not produce a node commit.
        return [Artifact(
            id=f"art_{task.node_id}", run_id=task.run_id, type="result",
            content="read", lineage=Lineage(produced_by=task.node_id),
        )]

    orch = _orch(**{
        "local://coder": _writer("a.txt", "1"),
        "local://check": reader,
    })
    wf = {
        "name": "proj", "workspace": {"source": "empty"},
        "nodes": {
            "coder": {"agent": "local://coder", "outputs": ["o"], "workspace": "write"},
            "check": {"agent": "local://check", "outputs": ["o"],
                      "workspace": "read", "depends_on": ["coder"]},
        },
    }
    summary = await orch.run_workflow(wf)
    assert summary.status == "completed"
    ws = orch._workspace
    # Only the coder's commit exists (plus baseline); the reader made none.
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=ws.root, capture_output=True, text=True,
    ).stdout.strip().splitlines()
    assert len([ln for ln in log if "node:" in ln]) == 1
    ws.cleanup()


@pytest.mark.asyncio
async def test_no_workspace_means_no_root_injected(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    seen = {}

    async def probe(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
        seen["root"] = task.config.get("_workspace_root")
        return [Artifact(id="a", run_id=task.run_id, type="result", content="x",
                         lineage=Lineage(produced_by=task.node_id))]

    orch = _orch(**{"local://p": probe})
    wf = {"name": "no-ws", "nodes": {"n": {"agent": "local://p", "outputs": ["o"]}}}
    summary = await orch.run_workflow(wf)
    assert summary.status == "completed"
    assert orch._workspace is None
    assert seen["root"] is None
