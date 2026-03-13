"""LangChain framework adapter and plugin."""

from __future__ import annotations

import asyncio
import importlib.util
from typing import Any

from binex.adapters.framework_base import BaseFrameworkAdapter


class LangChainAdapter(BaseFrameworkAdapter):
    """Adapter for LangChain Runnables (chains, agents, tools)."""

    _prefix: str = "langchain"

    def _validate(self, obj: Any) -> None:
        """Validate that obj has .invoke method."""
        if not hasattr(obj, "invoke"):
            raise ValueError(
                f"langchain://{self._import_path} failed: "
                f"object has no 'invoke' method — expected a LangChain Runnable"
            )

    async def _invoke(self, obj: Any, input_data: Any) -> Any:
        """Call ainvoke if available, else fall back to sync invoke in a thread."""
        if hasattr(obj, "ainvoke") and asyncio.iscoroutinefunction(obj.ainvoke):
            return await obj.ainvoke(input_data)
        return await asyncio.to_thread(obj.invoke, input_data)

    def _extract_output(self, result: Any) -> Any:
        """Passthrough — return result as-is."""
        return result


class LangChainPlugin:
    """Plugin entry point for LangChain adapter registration."""

    prefix: str = "langchain"

    def create_adapter(self, uri: str, config: dict[str, Any]) -> LangChainAdapter:
        """Create a LangChainAdapter after verifying langchain_core is installed."""
        if importlib.util.find_spec("langchain_core") is None:
            raise ImportError(
                "LangChain integration requires langchain-core. "
                "Install it with: pip install binex[langchain]"
            )
        return LangChainAdapter(import_path=uri, config=config)
