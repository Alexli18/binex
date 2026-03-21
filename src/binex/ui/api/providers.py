"""Providers API — list LLM providers with configuration status and models."""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from binex.cli.providers import PROVIDERS

router = APIRouter(prefix="/providers", tags=["providers"])

# ---------------------------------------------------------------------------
# Curated model lists per provider
# ---------------------------------------------------------------------------

_CURATED_MODELS: dict[str, list[dict[str, Any]]] = {
    "openai": [
        {"id": "gpt-4o", "tier": "flagship", "context_k": 128},
        {"id": "gpt-4o-mini", "tier": "fast", "context_k": 128},
        {"id": "o3-mini", "tier": "reasoning", "context_k": 200},
    ],
    "anthropic": [
        {"id": "claude-opus-4-6", "tier": "flagship", "context_k": 200},
        {"id": "claude-sonnet-4-6", "tier": "balanced", "context_k": 200},
        {"id": "claude-haiku-4-5", "tier": "fast", "context_k": 200},
    ],
    "gemini": [
        {"id": "gemini-2.5-pro", "tier": "flagship", "context_k": 1000},
        {"id": "gemini-2.5-flash", "tier": "fast", "context_k": 1000},
    ],
    "ollama": [
        {"id": "llama3.3", "tier": "flagship", "context_k": 128},
        {"id": "qwen3", "tier": "balanced", "context_k": 128},
        {"id": "gemma3", "tier": "fast", "context_k": 128},
    ],
    "groq": [
        {"id": "llama-3.3-70b-versatile", "tier": "flagship", "context_k": 128},
        {"id": "llama-3.1-8b-instant", "tier": "fast", "context_k": 128},
    ],
    "deepseek": [
        {"id": "deepseek-chat", "tier": "balanced", "context_k": 64},
        {"id": "deepseek-reasoner", "tier": "reasoning", "context_k": 64},
    ],
    "mistral": [
        {"id": "mistral-large-latest", "tier": "flagship", "context_k": 128},
        {"id": "mistral-small-latest", "tier": "fast", "context_k": 128},
    ],
    "openrouter": [
        {"id": "google/gemini-2.5-flash", "tier": "fast", "context_k": 1000},
        {"id": "meta-llama/llama-4-maverick", "tier": "flagship", "context_k": 128},
        {"id": "google/gemma-3-27b-it:free", "tier": "free", "context_k": 96},
    ],
    "together": [
        {"id": "meta-llama/Llama-3-70b", "tier": "flagship", "context_k": 8},
    ],
}

_OLLAMA_TIMEOUT = 2.0  # seconds


async def _fetch_ollama_models() -> list[dict[str, Any]] | None:
    """Try to fetch models from a local Ollama instance.

    Returns a list of model dicts or ``None`` on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=_OLLAMA_TIMEOUT) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code != 200:
                return None
            data = resp.json()
            models = data.get("models", [])
            return [
                {"id": m.get("name", "unknown"), "tier": "local", "context_k": None}
                for m in models
            ]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# GET /providers
# ---------------------------------------------------------------------------

@router.get("")
async def list_providers() -> JSONResponse:
    """List all supported LLM providers with config status and models."""
    result = []

    for name, cfg in PROVIDERS.items():
        configured = (
            cfg.env_var is None
            or bool(os.environ.get(cfg.env_var))
        )

        # Ollama: try live model list, fallback to curated
        if name == "ollama":
            live_models = await _fetch_ollama_models()
            models = live_models if live_models is not None else _CURATED_MODELS.get(name, [])
            # If live models returned, Ollama is running → configured
            if live_models is not None:
                configured = True
        else:
            models = _CURATED_MODELS.get(name, [])

        result.append({
            "name": name,
            "default_model": cfg.default_model,
            "env_var": cfg.env_var,
            "agent_prefix": cfg.agent_prefix,
            "configured": configured,
            "models": models,
        })

    return JSONResponse({"providers": result})
