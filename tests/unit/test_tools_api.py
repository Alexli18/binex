"""Tests for built-in tools API endpoint."""

import pytest
from fastapi.testclient import TestClient

from binex.ui.server import create_app


@pytest.fixture()
def client():
    app = create_app(dev=True)
    return TestClient(app)


def test_list_builtin_tools(client):
    resp = client.get("/api/v1/tools/builtins")
    assert resp.status_code == 200
    data = resp.json()
    assert "tools" in data
    tools = data["tools"]
    assert len(tools) == 10

    names = {t["name"] for t in tools}
    assert "calculator" in names
    assert "web_search" in names
    assert "shell_command" in names

    # Check structure
    for t in tools:
        assert "name" in t
        assert "description" in t
        assert "category" in t
        assert t["category"] in ("data", "web", "files", "system")


def test_builtin_tools_categories(client):
    resp = client.get("/api/v1/tools/builtins")
    tools = resp.json()["tools"]

    by_cat = {}
    for t in tools:
        by_cat.setdefault(t["category"], []).append(t["name"])

    assert len(by_cat["data"]) == 4
    assert len(by_cat["web"]) == 3
    assert len(by_cat["files"]) == 2
    assert len(by_cat["system"]) == 1
