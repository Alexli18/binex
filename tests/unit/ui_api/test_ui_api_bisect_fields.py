"""The bisect endpoint must carry field-level detail and the judge verdict.

The web UI otherwise sees only a similarity number — the same thing that made
the CLI output useless for structured content.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus


async def _seed(stores, good: Any, bad: Any) -> None:
    exec_store, art_store = stores
    for run_id, content in (("good", good), ("bad", bad)):
        await exec_store.create_run(RunSummary(
            run_id=run_id, workflow_name="wf", status="completed",
            total_nodes=1, completed_nodes=1,
        ))
        await art_store.store(Artifact(
            id=f"art_{run_id}", run_id=run_id, type="result", content=content,
            lineage=Lineage(produced_by="review"),
        ))
        await exec_store.record(ExecutionRecord(
            id=f"rec_{run_id}", run_id=run_id, task_id="review",
            agent_id="llm://gpt-4o", status=TaskStatus.COMPLETED,
            output_artifact_refs=[f"art_{run_id}"], latency_ms=10,
            trace_id=f"trace_{run_id}",
        ))


async def _post(client, stores):
    with patch("binex.ui.api.bisect._get_stores", return_value=stores):
        resp = await client.post(
            "/api/v1/bisect", json={"good_run": "good", "bad_run": "bad"},
        )
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_structured_node_reports_changed_fields(client, stores):
    await _seed(
        stores,
        {"decision": "approved", "reason": "all checks passed"},
        {"decision": "rejected", "reason": "all checks passed"},
    )

    data = await _post(client, stores)

    node = data["node_map"][0]
    assert node["field_changes"] == [
        {
            "path": "decision",
            "before": "approved",
            "after": "rejected",
            "kind": "changed",
        },
    ]
    assert data["details"]["field_changes"] == node["field_changes"]


@pytest.mark.asyncio
async def test_text_node_has_no_field_changes(client, stores):
    await _seed(stores, "the report is ready", "the report is done")

    data = await _post(client, stores)

    assert data["node_map"][0]["field_changes"] is None
    assert data["details"]["diff"] is not None


@pytest.mark.asyncio
async def test_reordered_keys_are_not_a_divergence(client, stores):
    await _seed(stores, {"a": 1, "b": 2}, {"b": 2, "a": 1})

    data = await _post(client, stores)

    assert data["divergence_node"] is None
    assert data["node_map"][0]["field_changes"] == []


@pytest.mark.asyncio
async def test_semantic_verdict_is_exposed(client, stores):
    """Without --semantic nothing judged, so the field is present but null."""
    await _seed(stores, "the report is ready", "the report is done")

    data = await _post(client, stores)

    assert "semantic_verdict" in data["node_map"][0]
    assert data["node_map"][0]["semantic_verdict"] is None
    assert "semantic_reason" in data["details"]
