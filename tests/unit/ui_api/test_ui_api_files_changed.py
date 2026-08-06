"""Tests for the workspace files-changed API endpoint (#75 UI)."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from binex.runtime.workspace import DEFAULT_BASE_DIR, Workspace, WorkspaceConfig
from binex.ui.server import create_app


@pytest.fixture
async def client():
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_files_changed_for_workspace_run(client, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)  # workspace resolves under cwd/.binex/workspaces
    ws = Workspace.create("run_ws", WorkspaceConfig(), base_dir=DEFAULT_BASE_DIR)
    ws.write_file("src/main.py", "print(1)")
    ws.snapshot("coder")
    ws.write_file("README.md", "hi")
    ws.snapshot("writer")

    resp = await client.get("/api/v1/runs/run_ws/files-changed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_workspace"] is True
    assert data["nodes"] == {"coder": ["src/main.py"], "writer": ["README.md"]}


@pytest.mark.asyncio
async def test_files_changed_no_workspace(client, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resp = await client.get("/api/v1/runs/run_none/files-changed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_workspace"] is False
    assert data["nodes"] == {}
    assert not Path(DEFAULT_BASE_DIR).joinpath("run_none").exists()
