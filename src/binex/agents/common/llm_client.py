"""Shared LLM client wrapping LiteLLM for reference agents."""

from __future__ import annotations

from typing import Any

import litellm

from binex.agents.common.llm_config import LLMConfig


class LLMClient:
    """Async LLM client using LiteLLM for unified provider access."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self._config = config or LLMConfig()

    @property
    def config(self) -> LLMConfig:
        return self._config

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a completion request and return the response text."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "temperature": temperature or self._config.temperature,
            "max_tokens": max_tokens or self._config.max_tokens,
        }
        if self._config.api_base:
            kwargs["api_base"] = self._config.api_base
        if self._config.api_key:
            kwargs["api_key"] = self._config.api_key

        response = await litellm.acompletion(**kwargs)
        return response.choices[0].message.content or ""

    async def complete_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
    ) -> str:
        """Send a completion request expecting JSON output."""
        suffix = "\nRespond with valid JSON only. No markdown, no extra text."
        json_system = (system or "") + suffix
        return await self.complete(prompt, system=json_system.strip())
