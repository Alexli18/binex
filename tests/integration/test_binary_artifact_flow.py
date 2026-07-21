"""Integration: a binary artifact flows through the DAG intact (#76)."""

from __future__ import annotations

from pathlib import Path

import pytest

from binex.adapters.local import LocalPythonAdapter
from binex.artifacts.binary import is_binary_artifact, load_blob, make_binary_artifact
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore

_IMG = b"\x89PNG\r\n\x1a\n" + b"data" * 50


@pytest.mark.asyncio
async def test_binary_artifact_flows_to_downstream(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BINEX_STORE_PATH", str(tmp_path / ".binex"))

    async def generator(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
        return [make_binary_artifact(task.run_id, task.node_id, _IMG, "image/png")]

    received: dict[str, Artifact] = {}

    async def consumer(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
        received["art"] = inputs[0]
        return [Artifact(id="c", run_id=task.run_id, type="result", content="done",
                         lineage=Lineage(produced_by=task.node_id))]

    orch = Orchestrator(
        artifact_store=InMemoryArtifactStore(),
        execution_store=InMemoryExecutionStore(),
    )
    orch.dispatcher.register_adapter("local://gen", LocalPythonAdapter(handler=generator))
    orch.dispatcher.register_adapter("local://use", LocalPythonAdapter(handler=consumer))

    wf = {
        "name": "media",
        "nodes": {
            "gen": {"agent": "local://gen", "outputs": ["img"]},
            "use": {"agent": "local://use", "outputs": ["out"], "depends_on": ["gen"]},
        },
    }
    summary = await orch.run_workflow(wf)
    assert summary.status == "completed"

    art = received["art"]
    assert is_binary_artifact(art)
    assert art.content["mime"] == "image/png"
    # The payload survived — the blob is readable and byte-identical.
    assert load_blob(art.content) == _IMG
    assert Path(art.content["path"]).exists()
