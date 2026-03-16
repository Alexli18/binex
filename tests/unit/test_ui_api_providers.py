"""Tests for the providers API endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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


# ---------------------------------------------------------------------------
# GET /providers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_providers_returns_all(client):
    """GET /providers returns all 9 providers."""
    resp = await client.get("/api/v1/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    names = [p["name"] for p in data["providers"]]
    for expected in ("openai", "anthropic", "gemini", "ollama", "groq",
                     "deepseek", "mistral", "openrouter", "together"):
        assert expected in names


@pytest.mark.asyncio
async def test_provider_fields(client):
    """Each provider has required fields."""
    resp = await client.get("/api/v1/providers")
    for p in resp.json()["providers"]:
        assert "name" in p
        assert "default_model" in p
        assert "agent_prefix" in p
        assert "configured" in p
        assert "models" in p
        assert isinstance(p["configured"], bool)
        assert isinstance(p["models"], list)


@pytest.mark.asyncio
async def test_model_fields(client):
    """Each model has id and tier fields."""
    resp = await client.get("/api/v1/providers")
    for p in resp.json()["providers"]:
        for m in p["models"]:
            assert "id" in m
            assert "tier" in m


@pytest.mark.asyncio
async def test_configured_reflects_env(client, monkeypatch):
    """Provider with env_var set → configured=True, unset → False."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    resp = await client.get("/api/v1/providers")
    openai_p = next(p for p in resp.json()["providers"] if p["name"] == "openai")
    assert openai_p["configured"] is False

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    resp2 = await client.get("/api/v1/providers")
    openai_p2 = next(p for p in resp2.json()["providers"] if p["name"] == "openai")
    assert openai_p2["configured"] is True


@pytest.mark.asyncio
async def test_ollama_no_env_var_needed(client, monkeypatch):
    """Ollama has no env_var, so env_var should be null."""
    resp = await client.get("/api/v1/providers")
    ollama_p = next(p for p in resp.json()["providers"] if p["name"] == "ollama")
    assert ollama_p["env_var"] is None


@pytest.mark.asyncio
async def test_ollama_live_models(client):
    """When Ollama is running, live models are returned."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "models": [
            {"name": "llama3:latest"},
            {"name": "mistral:latest"},
        ]
    }

    with patch("binex.ui.api.providers._fetch_ollama_models") as mock_fetch:
        mock_fetch.return_value = [
            {"id": "llama3:latest", "tier": "local", "context_k": None},
            {"id": "mistral:latest", "tier": "local", "context_k": None},
        ]
        resp = await client.get("/api/v1/providers")

    ollama_p = next(p for p in resp.json()["providers"] if p["name"] == "ollama")
    assert ollama_p["configured"] is True
    model_ids = [m["id"] for m in ollama_p["models"]]
    assert "llama3:latest" in model_ids
    assert "mistral:latest" in model_ids


@pytest.mark.asyncio
async def test_ollama_fallback_curated(client):
    """When Ollama is not running, curated models are returned."""
    with patch("binex.ui.api.providers._fetch_ollama_models") as mock_fetch:
        mock_fetch.return_value = None
        resp = await client.get("/api/v1/providers")

    ollama_p = next(p for p in resp.json()["providers"] if p["name"] == "ollama")
    model_ids = [m["id"] for m in ollama_p["models"]]
    assert "llama3.3" in model_ids


@pytest.mark.asyncio
async def test_curated_models_openai(client):
    """OpenAI has expected curated models."""
    resp = await client.get("/api/v1/providers")
    openai_p = next(p for p in resp.json()["providers"] if p["name"] == "openai")
    model_ids = [m["id"] for m in openai_p["models"]]
    assert "gpt-4o" in model_ids
    assert "gpt-4o-mini" in model_ids
    assert "o3-mini" in model_ids


@pytest.mark.asyncio
async def test_curated_models_anthropic(client):
    """Anthropic has expected curated models."""
    resp = await client.get("/api/v1/providers")
    anthropic_p = next(p for p in resp.json()["providers"] if p["name"] == "anthropic")
    model_ids = [m["id"] for m in anthropic_p["models"]]
    assert "claude-opus-4-6" in model_ids
    assert "claude-sonnet-4-6" in model_ids
    assert "claude-haiku-4-5" in model_ids
