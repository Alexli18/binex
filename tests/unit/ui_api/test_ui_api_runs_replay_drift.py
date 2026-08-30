"""POST /api/v1/runs/replay must reject stale cached upstream, not reuse it silently."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.models.workflow import WorkflowSpec

WORKFLOW_YAML = """\
name: replay-test
nodes:
  builder:
    agent: "local://echo"
    system_prompt: build
    outputs: [draft]
  reviewer:
    agent: "local://echo"
    system_prompt: review
    outputs: [review]
    depends_on: [builder]
"""

EDITED_WORKFLOW_YAML = WORKFLOW_YAML.replace(
    "system_prompt: build", "system_prompt: build, but rewritten",
)


@pytest.fixture
def workflow_file(tmp_path: Path) -> Path:
    path = tmp_path / "replay-test.yaml"
    path.write_text(EDITED_WORKFLOW_YAML)
    return path


async def _seed_original_run(stores) -> None:
    """Seed a completed run whose snapshot holds the *original* builder prompt."""
    exec_store, art_store = stores
    spec = WorkflowSpec(**yaml.safe_load(WORKFLOW_YAML))
    workflow_hash = await exec_store.store_workflow_snapshot(
        yaml.dump(spec.model_dump(exclude={"source_path"}), sort_keys=True),
        version=spec.version,
    )
    await exec_store.create_run(
        RunSummary(
            run_id="run-orig",
            workflow_name="replay-test",
            status="completed",
            total_nodes=2,
            workflow_hash=workflow_hash,
        )
    )
    await art_store.store(
        Artifact(
            id="art-draft", run_id="run-orig", type="draft", content="v1",
            lineage=Lineage(produced_by="builder"),
        )
    )
    await exec_store.record(
        ExecutionRecord(
            id="rec-builder", run_id="run-orig", task_id="builder",
            agent_id="local://echo", status=TaskStatus.COMPLETED,
            output_artifact_refs=["art-draft"], latency_ms=5,
            trace_id="trace-orig",
        )
    )


@pytest.mark.asyncio
async def test_drifted_upstream_returns_409(client, stores, workflow_file):
    """A changed cached node is a conflict, not a generic replay failure."""
    await _seed_original_run(stores)

    with patch("binex.ui.api.runs._get_stores", return_value=stores):
        resp = await client.post(
            "/api/v1/runs/replay",
            json={
                "run_id": "run-orig",
                "from_step": "reviewer",
                "workflow_path": str(workflow_file),
            },
        )

    assert resp.status_code == 409
    body = resp.json()
    assert body["error_code"] == "workflow_drift"
    assert "builder" in body["error"]


@pytest.mark.asyncio
async def test_allow_drift_replays_anyway(client, stores, workflow_file):
    """The client can opt into reusing the stale cached output."""
    await _seed_original_run(stores)

    with patch("binex.ui.api.runs._get_stores", return_value=stores):
        resp = await client.post(
            "/api/v1/runs/replay",
            json={
                "run_id": "run-orig",
                "from_step": "reviewer",
                "workflow_path": str(workflow_file),
                "allow_drift": True,
            },
        )

    assert resp.status_code == 201
    assert resp.json()["status"] == "completed"
