"""The diff endpoint must forward field-level detail to the web UI.

`_reshape_for_frontend` picks specific keys out of the core diff result, so a new
key is invisible to the UI until it is listed there.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus


async def _seed(stores, good_content: Any, bad_content: Any) -> None:
    exec_store, art_store = stores
    for run_id, content in (("good", good_content), ("bad", bad_content)):
        await exec_store.create_run(RunSummary(
            run_id=run_id, workflow_name="wf", status="completed",
            total_nodes=1, completed_nodes=1,
        ))
        await art_store.store(Artifact(
            id=f"art_{run_id}", run_id=run_id, type="result", content=content,
            lineage=Lineage(produced_by="n"),
        ))
        await exec_store.record(ExecutionRecord(
            id=f"rec_{run_id}", run_id=run_id, task_id="n",
            agent_id="local://echo", status=TaskStatus.COMPLETED,
            output_artifact_refs=[f"art_{run_id}"], latency_ms=10,
            trace_id=f"trace_{run_id}",
        ))


async def _post_diff(client, stores):
    with patch("binex.ui.api.diff._get_stores", return_value=stores):
        resp = await client.post(
            "/api/v1/diff", json={"run_a": "good", "run_b": "bad"},
        )
    assert resp.status_code == 200
    return resp.json()["node_diffs"][0]


@pytest.mark.asyncio
async def test_changed_field_reaches_the_ui(client, stores):
    await _seed(
        stores,
        {"decision": "approved", "reason": "all checks passed"},
        {"decision": "rejected", "reason": "all checks passed"},
    )

    node = await _post_diff(client, stores)

    assert node["field_changes"] == [
        {
            "path": "decision",
            "before": "approved",
            "after": "rejected",
            "kind": "changed",
        },
    ]
    assert node["content_similarity"] == 0.5


@pytest.mark.asyncio
async def test_reordered_keys_report_no_change(client, stores):
    await _seed(stores, {"a": 1, "b": 2}, {"b": 2, "a": 1})

    node = await _post_diff(client, stores)

    assert node["field_changes"] == []
    assert node["content_similarity"] == 1.0
    # artifact_diff drives the UI's "show diff" affordance — nothing to show.
    assert node["artifact_diff"] is None


@pytest.mark.asyncio
async def test_text_content_has_no_field_changes(client, stores):
    await _seed(stores, "hello there", "hello world")

    node = await _post_diff(client, stores)

    assert node["field_changes"] is None
    assert node["artifact_diff"] is not None
