"""Tests for POST /api/v1/runs/replay — full-run replay endpoint (runs.py)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus

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


@pytest.fixture
def workflow_file(tmp_path: Path) -> Path:
    path = tmp_path / "replay-test.yaml"
    path.write_text(WORKFLOW_YAML)
    return path


async def _seed_original_run(stores) -> None:
    """Seed a completed 2-node run: builder executed, its artifact stored."""
    exec_store, art_store = stores
    await exec_store.create_run(
        RunSummary(
            run_id="run-orig",
            workflow_name="replay-test",
            status="completed",
            total_nodes=2,
        )
    )
    await art_store.store(
        Artifact(
            id="art-draft",
            run_id="run-orig",
            type="draft",
            content="v1",
            lineage=Lineage(produced_by="builder"),
        )
    )
    await exec_store.record(
        ExecutionRecord(
            id="rec-builder",
            run_id="run-orig",
            task_id="builder",
            agent_id="local://echo",
            status=TaskStatus.COMPLETED,
            output_artifact_refs=["art-draft"],
            latency_ms=5,
            trace_id="trace-orig",
        )
    )


@pytest.mark.asyncio
async def test_replay_happy_path_caches_upstream_and_reexecutes(
    client, stores, workflow_file
):
    await _seed_original_run(stores)
    exec_store, _ = stores

    with patch("binex.ui.api.runs._get_stores", return_value=stores):
        resp = await client.post(
            "/api/v1/runs/replay",
            json={
                "run_id": "run-orig",
                "from_step": "reviewer",
                "workflow_path": str(workflow_file),
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "completed"
    new_run_id = body["run_id"]
    assert new_run_id != "run-orig"

    new_run = await exec_store.get_run(new_run_id)
    assert new_run is not None
    assert new_run.forked_from == "run-orig"
    assert new_run.forked_at_step == "reviewer"
    assert new_run.status == "completed"
    assert new_run.completed_nodes == 2

    records = await exec_store.list_records(new_run_id)
    by_task = {r.task_id: r for r in records}
    # builder is upstream of from_step: copied from the original, not re-run
    assert by_task["builder"].output_artifact_refs == ["art-draft"]
    assert by_task["builder"].latency_ms == 0
    # reviewer actually re-executed
    assert by_task["reviewer"].status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_replay_unknown_workflow_returns_404(client):
    resp = await client.post(
        "/api/v1/runs/replay",
        json={
            "run_id": "run-orig",
            "from_step": "reviewer",
            "workflow_path": "/nonexistent/wf.yaml",
        },
    )

    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "workflow_not_found"
    assert "/nonexistent/wf.yaml" in body["error"]


@pytest.mark.asyncio
async def test_replay_missing_original_run_returns_422(
    client, stores, workflow_file
):
    with patch("binex.ui.api.runs._get_stores", return_value=stores):
        resp = await client.post(
            "/api/v1/runs/replay",
            json={
                "run_id": "run-ghost",
                "from_step": "reviewer",
                "workflow_path": str(workflow_file),
            },
        )

    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "replay_failed"
    assert "run-ghost" in body["error"]


@pytest.mark.asyncio
async def test_replay_unknown_from_step_returns_422(
    client, stores, workflow_file
):
    await _seed_original_run(stores)

    with patch("binex.ui.api.runs._get_stores", return_value=stores):
        resp = await client.post(
            "/api/v1/runs/replay",
            json={
                "run_id": "run-orig",
                "from_step": "nonexistent-step",
                "workflow_path": str(workflow_file),
            },
        )

    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "replay_failed"
    assert "nonexistent-step" in body["error"]
