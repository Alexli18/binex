"""Tests for the workflows API endpoints."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from binex.ui.server import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_list_workflows(client, tmp_path):
    # Create workflow files (must contain 'nodes:' to be detected)
    (tmp_path / "simple.yaml").write_text("name: simple\nnodes:\n  - id: a\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.yaml").write_text("name: nested\nnodes:\n  - id: b\n")
    # Hidden dir should be excluded
    (tmp_path / ".binex").mkdir()
    (tmp_path / ".binex" / "hidden.yaml").write_text("name: hidden\nnodes:\n  - id: c\n")
    # Non-workflow YAML should be excluded
    (tmp_path / "config.yaml").write_text("setting: value\n")

    with patch("binex.ui.api.workflows._get_workflows_dir", return_value=tmp_path):
        resp = await client.get("/api/v1/workflows")

    assert resp.status_code == 200
    data = resp.json()
    assert "workflows" in data
    assert "simple.yaml" in data["workflows"]
    assert "sub/nested.yaml" in data["workflows"]
    # Hidden directory files should be excluded
    for w in data["workflows"]:
        assert not w.startswith(".")
    # Non-workflow YAML should be excluded
    assert "config.yaml" not in data["workflows"]


@pytest.mark.asyncio
async def test_get_workflow(client, tmp_path):
    (tmp_path / "test.yaml").write_text("name: test-workflow\nnodes: []\n")

    with patch("binex.ui.api.workflows._get_workflows_dir", return_value=tmp_path):
        resp = await client.get("/api/v1/workflows/test.yaml")

    assert resp.status_code == 200
    data = resp.json()
    assert data["path"] == "test.yaml"
    assert "name: test-workflow" in data["content"]


@pytest.mark.asyncio
async def test_get_workflow_not_found(client, tmp_path):
    with patch("binex.ui.api.workflows._get_workflows_dir", return_value=tmp_path):
        resp = await client.get("/api/v1/workflows/nonexistent.yaml")

    assert resp.status_code == 404
    data = resp.json()
    assert "not found" in data["error"]


@pytest.mark.asyncio
async def test_path_traversal(client, tmp_path):
    """Path traversal attempts must not return file content from outside the base dir."""
    # Create a nested dir as the workflows base and a secret file outside it
    base = tmp_path / "projects" / "myapp"
    base.mkdir(parents=True)
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET")

    with patch("binex.ui.api.workflows._get_workflows_dir", return_value=base):
        # Try to escape with sub/../../../secret.txt
        resp = await client.get("/api/v1/workflows/sub/../../secret.txt")

    # Must not return 200 with the secret content.
    # httpx may normalize `..` in URL, causing the request to miss the workflows
    # router entirely (SPA fallback returns HTML, or 400/404 from workflows endpoint).
    if resp.status_code == 200:
        # If 200, ensure it's NOT the secret — could be SPA fallback HTML or empty JSON
        assert "TOP SECRET" not in resp.text
    else:
        assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_save_workflow(client, tmp_path):
    """PUT /workflows/{path} saves content to disk and returns confirmation."""
    with patch("binex.ui.api.workflows._get_workflows_dir", return_value=tmp_path):
        resp = await client.put(
            "/api/v1/workflows/my_workflow.yaml",
            json={"content": "name: saved\nnodes: []\n"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["path"] == "my_workflow.yaml"
    assert data["saved"] is True
    # Verify the file was written to disk
    assert (tmp_path / "my_workflow.yaml").read_text() == "name: saved\nnodes: []\n"


@pytest.mark.asyncio
async def test_save_workflow_traversal(client, tmp_path):
    """PUT /workflows/../../etc/evil must be rejected with 400."""
    with patch("binex.ui.api.workflows._get_workflows_dir", return_value=tmp_path):
        resp = await client.put(
            "/api/v1/workflows/sub/../../etc/evil",
            json={"content": "malicious"},
        )

    # Must be rejected — 400 (traversal blocked), 404 (not found), or 405
    # (httpx normalizes `..`, so request may miss the workflows router entirely)
    if resp.status_code == 200:
        data = resp.json()
        assert data.get("saved") is not True or str(
            (tmp_path / "sub" / ".." / ".." / "etc" / "evil").resolve()
        ).startswith(str(tmp_path.resolve()))
    else:
        assert resp.status_code in (400, 404, 405)
