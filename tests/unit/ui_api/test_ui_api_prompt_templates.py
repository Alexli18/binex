"""Tests for the prompt templates API endpoints (CRUD)."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# GET /templates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_templates(client):
    """GET /prompts/templates returns a non-empty list with expected fields."""
    resp = await client.get("/api/v1/prompts/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert "templates" in data
    assert len(data["templates"]) > 0

    for t in data["templates"]:
        assert "name" in t
        assert "category" in t
        assert "description" in t
        assert t["category"] != ""


@pytest.mark.asyncio
async def test_list_templates_has_all_categories(client):
    """All known prompt categories should be present."""
    resp = await client.get("/api/v1/prompts/templates")
    categories = {t["category"] for t in resp.json()["templates"]}
    for expected in ("Development", "General", "Workflow"):
        assert expected in categories, f"Missing category: {expected}"


# ---------------------------------------------------------------------------
# GET /templates/{name}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_template_by_name(client):
    """GET /prompts/templates/{name} returns full content."""
    resp = await client.get("/api/v1/prompts/templates/gen-draft-writer")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "gen-draft-writer"
    assert data["category"] == "General"
    assert "content" in data
    assert len(data["content"]) > 0


@pytest.mark.asyncio
async def test_get_template_not_found(client):
    """GET /prompts/templates/{name} returns 404 for unknown template."""
    resp = await client.get("/api/v1/prompts/templates/nonexistent-template")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_wf_prompts_categorized_as_workflow(client):
    """wf-* prompts should be in Workflow category."""
    resp = await client.get("/api/v1/prompts/templates")
    wf_templates = [t for t in resp.json()["templates"] if t["name"].startswith("wf-")]
    assert len(wf_templates) > 0
    for t in wf_templates:
        assert t["category"] == "Workflow"


# ---------------------------------------------------------------------------
# POST /templates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_prompt(client):
    """POST /prompts/templates creates a new prompt file."""
    body = {"name": "test-crud-create", "category": "General", "content": "Test prompt content."}
    resp = await client.post("/api/v1/prompts/templates", json=body)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "gen-test-crud-create"
    assert data["category"] == "General"

    # Verify it appears in list
    list_resp = await client.get("/api/v1/prompts/templates")
    names = [t["name"] for t in list_resp.json()["templates"]]
    assert "gen-test-crud-create" in names

    # Cleanup
    await client.delete("/api/v1/prompts/templates/gen-test-crud-create")


@pytest.mark.asyncio
async def test_create_prompt_invalid_category(client):
    """POST with invalid category returns 422."""
    body = {"name": "test-bad", "category": "InvalidCat", "content": "x"}
    resp = await client.post("/api/v1/prompts/templates", json=body)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_prompt_invalid_name(client):
    """POST with invalid name returns 422."""
    body = {"name": "Bad Name!", "category": "General", "content": "x"}
    resp = await client.post("/api/v1/prompts/templates", json=body)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_prompt_duplicate(client):
    """POST with existing name returns 409."""
    body = {"name": "test-dup", "category": "General", "content": "first"}
    resp1 = await client.post("/api/v1/prompts/templates", json=body)
    assert resp1.status_code == 201

    resp2 = await client.post("/api/v1/prompts/templates", json=body)
    assert resp2.status_code == 409

    # Cleanup
    await client.delete("/api/v1/prompts/templates/gen-test-dup")


# ---------------------------------------------------------------------------
# PUT /templates/{name}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_prompt(client):
    """PUT /prompts/templates/{name} updates content."""
    # Create first
    await client.post(
        "/api/v1/prompts/templates",
        json={"name": "test-update", "category": "Development", "content": "original"},
    )

    resp = await client.put(
        "/api/v1/prompts/templates/dev-test-update",
        json={"content": "updated content"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "updated"

    # Verify content changed
    get_resp = await client.get("/api/v1/prompts/templates/dev-test-update")
    assert get_resp.json()["content"] == "updated content"

    # Cleanup
    await client.delete("/api/v1/prompts/templates/dev-test-update")


@pytest.mark.asyncio
async def test_update_prompt_not_found(client):
    """PUT on nonexistent template returns 404."""
    resp = await client.put(
        "/api/v1/prompts/templates/nonexistent",
        json={"content": "x"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /templates/{name}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_prompt(client):
    """DELETE /prompts/templates/{name} removes the file."""
    await client.post(
        "/api/v1/prompts/templates",
        json={"name": "test-delete", "category": "General", "content": "temp"},
    )

    resp = await client.delete("/api/v1/prompts/templates/gen-test-delete")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    # Verify gone
    get_resp = await client.get("/api/v1/prompts/templates/gen-test-delete")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_prompt_not_found(client):
    """DELETE on nonexistent template returns 404."""
    resp = await client.delete("/api/v1/prompts/templates/nonexistent")
    assert resp.status_code == 404
