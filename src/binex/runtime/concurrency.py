"""Concurrency limiting for node execution.

Wide fan-out (e.g. a scatter pattern with N=50 workers) would otherwise fire
N simultaneous LLM calls and trip provider rate limits. ``ConcurrencyLimiter``
caps in-flight node execution globally and, optionally, per provider — so a
local Ollama (1 GPU) and a hosted API can have very different tolerances in the
same workflow. See issue #55.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


def provider_of(agent: str) -> str:
    """Extract the provider key from an agent URI.

    ``llm://openai/gpt-4o`` -> ``openai``, ``ollama/llama3`` style models keep
    their leading segment, and non-LLM agents fall back to their URI scheme
    (``local://`` -> ``local``, ``a2a://`` -> ``a2a``).
    """
    if agent.startswith("llm://"):
        model = agent.removeprefix("llm://")
        return model.split("/", 1)[0] if "/" in model else model
    if "://" in agent:
        return agent.split("://", 1)[0]
    return agent


class ConcurrencyLimiter:
    """Caps concurrent node execution globally and optionally per provider."""

    def __init__(
        self,
        global_limit: int,
        provider_limits: dict[str, int] | None = None,
    ) -> None:
        self.global_limit = global_limit
        self.provider_limits = dict(provider_limits or {})
        self._global = asyncio.Semaphore(global_limit)
        self._providers = {
            provider: asyncio.Semaphore(limit)
            for provider, limit in self.provider_limits.items()
        }

    @classmethod
    def from_spec(
        cls,
        concurrency: int | dict[str, int] | None,
        default_limit: int,
    ) -> ConcurrencyLimiter:
        """Build from a ``WorkflowSpec.concurrency`` value.

        A bare int is the global cap. A dict uses its ``default`` key as the
        global cap (falling back to ``default_limit``) and every other key as a
        per-provider cap.
        """
        if isinstance(concurrency, int):
            return cls(concurrency)
        if isinstance(concurrency, dict):
            global_limit = concurrency.get("default", default_limit)
            providers = {
                k: v for k, v in concurrency.items() if k != "default"
            }
            return cls(global_limit, providers)
        return cls(default_limit)

    @asynccontextmanager
    async def slot(self, agent: str) -> AsyncIterator[None]:
        """Hold a global slot, plus the provider slot if one is configured.

        Slots are always acquired global-then-provider, a fixed order, so nodes
        cannot deadlock waiting on each other's semaphores.
        """
        provider_sem = self._providers.get(provider_of(agent))
        async with self._global:
            if provider_sem is None:
                yield
            else:
                async with provider_sem:
                    yield
