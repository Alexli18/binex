"""AutoGen framework adapter and plugin for Binex."""

from __future__ import annotations

import asyncio
import importlib.util
from typing import Any

from binex.adapters.framework_base import BaseFrameworkAdapter


class AutoGenAdapter(BaseFrameworkAdapter):
    """Adapter that wraps an AutoGen agent object."""

    _prefix: str = "autogen"

    def _validate(self, obj: Any) -> None:
        """Validate that obj has a run method."""
        if not hasattr(obj, "run"):
            raise ValueError(
                f"AutoGen object at '{self._import_path}' must have a 'run' method"
            )

    async def _invoke(self, obj: Any, input_data: Any) -> Any:
        """Call a_run(task=) if available, else fall back to sync run in a thread."""
        if hasattr(obj, "a_run") and asyncio.iscoroutinefunction(obj.a_run):
            return await obj.a_run(task=input_data)
        return await asyncio.to_thread(obj.run, task=input_data)

    def _extract_output(self, result: Any) -> Any:
        """Extract from result.messages[-1] if available, otherwise str(result)."""
        if hasattr(result, "messages") and result.messages:
            message = result.messages[-1]
            if isinstance(message, str):
                return message
            if isinstance(message, dict) and "content" in message:
                return message["content"]
            return str(message)
        if result is None:
            return ""
        return str(result)


class AutoGenPlugin:
    """Plugin entry point for the AutoGen adapter."""

    prefix = "autogen"

    def create_adapter(self, uri: str, config: dict[str, Any]) -> AutoGenAdapter:
        """Create an AutoGenAdapter, raising ImportError if autogen is not installed."""
        if importlib.util.find_spec("autogen_agentchat") is None:
            raise ImportError(
                "autogen-agentchat is not installed. "
                "Install it with: pip install binex[autogen]"
            )
        return AutoGenAdapter(uri, config)
