"""Tests for the export API endpoint (run_ids/last_n modes, JSON and CSV/zip)."""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import CostRecord
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus


def _make_run(run_id: str = "run-1", **kwargs) -> RunSummary:
    defaults = dict(
        run_id=run_id,
        workflow_name="test-workflow",
        status="completed",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        total_nodes=3,
        completed_nodes=3,
    )
    defaults.update(kwargs)
    return RunSummary(**defaults)


def _patch_stores(stores):
    return patch("binex.ui.api.export._get_stores", return_value=stores)


async def _seed_full_run(stores, run_id: str = "run-full") -> None:
    """Run with one record, one cost record, and one artifact."""
    exec_store, art_store = stores
    await exec_store.create_run(_make_run(run_id))
    await exec_store.record(
        ExecutionRecord(
            id=f"rec-{run_id}",
            run_id=run_id,
            task_id="node-a",
            agent_id="local://echo",
            status=TaskStatus.COMPLETED,
            latency_ms=7,
            trace_id=f"trace-{run_id}",
        )
    )
    await exec_store.record_cost(
        CostRecord(
            id=f"cost-{run_id}",
            run_id=run_id,
            task_id="node-a",
            cost=0.01,
            source="llm_tokens",
        )
    )
    await art_store.store(
        Artifact(
            id=f"art-{run_id}",
            run_id=run_id,
            type="text",
            content="payload",
            lineage=Lineage(produced_by="node-a"),
        )
    )


@pytest.mark.asyncio
async def test_export_last_n_returns_most_recent(client, stores):
    exec_store, _ = stores
    # Inserted out of chronological order on purpose — last_n must sort
    # by started_at, not rely on store insertion order.
    await exec_store.create_run(
        _make_run("run-old", started_at=datetime(2026, 1, 1, tzinfo=UTC))
    )
    await exec_store.create_run(
        _make_run("run-newest", started_at=datetime(2026, 1, 3, tzinfo=UTC))
    )
    await exec_store.create_run(
        _make_run("run-mid", started_at=datetime(2026, 1, 2, tzinfo=UTC))
    )

    with _patch_stores(stores):
        resp = await client.post("/api/v1/export", json={"last_n": 2, "format": "json"})

    assert resp.status_code == 200
    data = resp.json()
    exported_ids = [r["run_id"] for r in data["runs"]]
    assert exported_ids == ["run-newest", "run-mid"]


@pytest.mark.asyncio
async def test_export_last_n_greater_than_total_exports_all(client, stores):
    exec_store, _ = stores
    await exec_store.create_run(_make_run("run-1"))
    await exec_store.create_run(
        _make_run("run-2", started_at=datetime(2026, 1, 2, tzinfo=UTC))
    )

    with _patch_stores(stores):
        resp = await client.post("/api/v1/export", json={"last_n": 10, "format": "json"})

    assert resp.status_code == 200
    data = resp.json()
    assert {r["run_id"] for r in data["runs"]} == {"run-1", "run-2"}


@pytest.mark.asyncio
async def test_export_both_run_ids_and_last_n_rejected(client, stores):
    with _patch_stores(stores):
        resp = await client.post(
            "/api/v1/export", json={"run_ids": ["run-1"], "last_n": 1}
        )

    assert resp.status_code == 422
    assert "exactly one" in resp.json()["error"]


@pytest.mark.asyncio
async def test_export_neither_run_ids_nor_last_n_rejected(client, stores):
    with _patch_stores(stores):
        resp = await client.post("/api/v1/export", json={})

    assert resp.status_code == 422
    assert "exactly one" in resp.json()["error"]


@pytest.mark.asyncio
async def test_export_last_n_zero_rejected(client, stores):
    with _patch_stores(stores):
        resp = await client.post("/api/v1/export", json={"last_n": 0})

    assert resp.status_code == 422
    assert "last_n" in resp.json()["error"]


@pytest.mark.asyncio
async def test_export_last_n_empty_store_returns_404(client, stores):
    with _patch_stores(stores):
        resp = await client.post("/api/v1/export", json={"last_n": 5})

    assert resp.status_code == 404
    assert resp.json()["error"] == "No runs found"


@pytest.mark.asyncio
async def test_export_run_ids_still_works(client, stores):
    exec_store, _ = stores
    await exec_store.create_run(_make_run("run-1"))

    with _patch_stores(stores):
        resp = await client.post(
            "/api/v1/export", json={"run_ids": ["run-1"], "format": "json"}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert [r["run_id"] for r in data["runs"]] == ["run-1"]


@pytest.mark.asyncio
async def test_export_empty_run_ids_rejected(client, stores):
    with _patch_stores(stores):
        resp = await client.post("/api/v1/export", json={"run_ids": []})

    assert resp.status_code == 422
    assert resp.json()["error"] == "run_ids must not be empty"


@pytest.mark.asyncio
async def test_export_unsupported_format_rejected(client, stores):
    with _patch_stores(stores):
        resp = await client.post(
            "/api/v1/export", json={"run_ids": ["run-1"], "format": "xml"}
        )

    assert resp.status_code == 422
    assert "Unsupported format: xml" in resp.json()["error"]


@pytest.mark.asyncio
async def test_export_mixed_found_and_missing_exports_found_only(client, stores):
    exec_store, _ = stores
    await exec_store.create_run(_make_run("run-real"))

    with _patch_stores(stores):
        resp = await client.post(
            "/api/v1/export",
            json={"run_ids": ["run-real", "run-ghost"], "format": "json"},
        )

    assert resp.status_code == 200
    assert [r["run_id"] for r in resp.json()["runs"]] == ["run-real"]


@pytest.mark.asyncio
async def test_export_json_include_artifacts(client, stores):
    await _seed_full_run(stores, "run-art")

    with _patch_stores(stores):
        resp = await client.post(
            "/api/v1/export",
            json={"run_ids": ["run-art"], "format": "json", "include_artifacts": True},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert [a["id"] for a in data["artifacts"]] == ["art-run-art"]
    assert data["artifacts"][0]["content"] == "payload"


@pytest.mark.asyncio
async def test_export_csv_returns_zip_with_three_csvs(client, stores):
    await _seed_full_run(stores, "run-csv")

    with _patch_stores(stores):
        resp = await client.post(
            "/api/v1/export", json={"run_ids": ["run-csv"], "format": "csv"}
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert "binex-export.zip" in resp.headers["content-disposition"]

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    assert set(zf.namelist()) == {"runs.csv", "records.csv", "costs.csv"}
    runs_csv = zf.read("runs.csv").decode().splitlines()
    assert runs_csv[0].startswith("run_id,")  # header row
    assert runs_csv[1].startswith("run-csv,")
    assert "node-a" in zf.read("records.csv").decode()
    assert "cost-run-csv" in zf.read("costs.csv").decode()


@pytest.mark.asyncio
async def test_export_csv_include_artifacts_adds_artifacts_json(client, stores):
    await _seed_full_run(stores, "run-zip-art")

    with _patch_stores(stores):
        resp = await client.post(
            "/api/v1/export",
            json={"run_ids": ["run-zip-art"], "format": "csv", "include_artifacts": True},
        )

    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    assert "artifacts.json" in zf.namelist()
    assert "art-run-zip-art" in zf.read("artifacts.json").decode()


@pytest.mark.asyncio
async def test_export_csv_run_without_costs_yields_empty_costs_csv(client, stores):
    exec_store, _ = stores
    await exec_store.create_run(_make_run("run-bare"))

    with _patch_stores(stores):
        resp = await client.post(
            "/api/v1/export", json={"run_ids": ["run-bare"], "format": "csv"}
        )

    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    # _write_csv returns "" for an empty row list — member exists but is empty
    assert zf.read("costs.csv") == b""
    assert zf.read("records.csv") == b""
