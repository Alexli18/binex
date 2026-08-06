"""Tests for the export API endpoint (run_ids and last_n modes)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from binex.models.execution import RunSummary


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
