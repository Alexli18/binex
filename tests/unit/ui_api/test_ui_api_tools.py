"""Tests for the built-in tools API endpoint."""

from __future__ import annotations

import pytest

# The public contract: 10 built-in tools, documented in CLAUDE.md and
# docs/. A hard equality is deliberate — adding/removing a tool must
# break this test so the docs and the _CATEGORIES map in
# binex/ui/api/tools.py get updated in the same change.
EXPECTED_TOOLS = {
    "calculator",
    "dice_roll",
    "fetch_url",
    "http_request",
    "web_search",
    "read_file",
    "write_file",
    "shell_command",
    "json_parse",
    "random_choice",
}

# "other" is the endpoint's fallback for tools missing from _CATEGORIES;
# excluded on purpose — every builtin must be explicitly categorized.
ALLOWED_CATEGORIES = {"data", "web", "files", "system"}


@pytest.mark.asyncio
async def test_list_builtin_tools_matches_documented_set(client):
    resp = await client.get("/api/v1/tools/builtins")

    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert {t["name"] for t in tools} == EXPECTED_TOOLS


@pytest.mark.asyncio
async def test_builtin_tools_shape_and_categories(client):
    resp = await client.get("/api/v1/tools/builtins")

    assert resp.status_code == 200
    for tool in resp.json()["tools"]:
        assert tool["name"]
        assert tool["description"]
        assert tool["category"] in ALLOWED_CATEGORIES
        assert isinstance(tool["parameters"], dict)
