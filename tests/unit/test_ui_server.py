"""Tests for the Binex Web UI FastAPI server."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from binex.ui.server import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_endpoint(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_health_returns_json_content_type(client):
    resp = await client.get("/api/v1/health")
    assert "application/json" in resp.headers["content-type"]


async def test_spa_fallback_serves_index_html(tmp_path, monkeypatch):
    """Unknown routes return index.html when static dir exists."""
    # Create a fake static dir with index.html
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    index_html = static_dir / "index.html"
    index_html.write_text("<html><body>Binex</body></html>")

    # Patch STATIC_DIR so create_app picks up our temp directory
    import binex.ui.server as server_module

    monkeypatch.setattr(server_module, "STATIC_DIR", static_dir)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Unknown route should serve index.html (SPA fallback)
        resp = await client.get("/runs/some-run-id")
        assert resp.status_code == 200
        assert "Binex" in resp.text

        # Root should also serve index.html
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "Binex" in resp.text


async def test_spa_fallback_serves_static_files(tmp_path, monkeypatch):
    """Static files are served directly when they exist."""
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html><body>Binex</body></html>")
    assets_dir = static_dir / "assets"
    assets_dir.mkdir()
    (assets_dir / "main.js").write_text("console.log('hello');")

    import binex.ui.server as server_module

    monkeypatch.setattr(server_module, "STATIC_DIR", static_dir)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/assets/main.js")
        assert resp.status_code == 200
        assert "hello" in resp.text


async def test_api_routes_not_caught_by_spa(tmp_path, monkeypatch):
    """API routes should still work when static dir exists."""
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html><body>Binex</body></html>")

    import binex.ui.server as server_module

    monkeypatch.setattr(server_module, "STATIC_DIR", static_dir)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
