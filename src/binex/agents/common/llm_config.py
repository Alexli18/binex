"""LLM configuration for reference agents."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """Configuration for LLM access via LiteLLM.

    Supports Ollama (local) and cloud providers via environment variables.
    """

    model: str = Field(
        default_factory=lambda: os.environ.get("BINEX_LLM_MODEL", "ollama/llama3.2")
    )
    api_base: str | None = Field(
        default_factory=lambda: os.environ.get("BINEX_LLM_API_BASE")
    )
    api_key: str | None = Field(
        default_factory=lambda: os.environ.get("BINEX_LLM_API_KEY")
    )
    temperature: float = Field(
        default_factory=lambda: float(os.environ.get("BINEX_LLM_TEMPERATURE", "0.7"))
    )
    max_tokens: int = Field(
        default_factory=lambda: int(os.environ.get("BINEX_LLM_MAX_TOKENS", "2048"))
    )

    @classmethod
    def for_ollama(
        cls, model: str = "llama3.2", base_url: str = "http://localhost:11434"
    ) -> LLMConfig:
        """Create config for local Ollama instance."""
        return cls(model=f"ollama/{model}", api_base=base_url)

    @classmethod
    def for_litellm_proxy(
        cls, model: str = "llama3.2", proxy_url: str = "http://localhost:4000"
    ) -> LLMConfig:
        """Create config targeting a LiteLLM proxy server."""
        return cls(model=model, api_base=proxy_url)
