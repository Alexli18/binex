"""CrewAI framework adapter and plugin for Binex."""

from __future__ import annotations

import asyncio
import importlib.util
from typing import Any

from binex.adapters.framework_base import BaseFrameworkAdapter


class CrewAIAdapter(BaseFrameworkAdapter):
    """Adapter that wraps a CrewAI Crew object."""

    _prefix: str = "crewai"

    def _validate(self, obj: Any) -> None:
        """Validate that obj has a kickoff method."""
        if not hasattr(obj, "kickoff"):
            raise ValueError(
                f"CrewAI object at '{self._import_path}' must have a 'kickoff' method"
            )

    async def _invoke(self, obj: Any, input_data: Any) -> Any:
        """Call kickoff_async if available, else fall back to sync kickoff in a thread."""
        if hasattr(obj, "kickoff_async") and asyncio.iscoroutinefunction(obj.kickoff_async):
            return await obj.kickoff_async(inputs=input_data)
        return await asyncio.to_thread(obj.kickoff, inputs=input_data)

    def _extract_output(self, result: Any) -> Any:
        """Extract .raw from CrewOutput, otherwise str()."""
        if result is None:
            return None
        if hasattr(result, "raw"):
            return result.raw
        return str(result)


class CrewAIPlugin:
    """Plugin entry point for the CrewAI adapter."""

    prefix = "crewai"

    def create_adapter(self, uri: str, config: dict[str, Any]) -> CrewAIAdapter:
        """Create a CrewAIAdapter, raising ImportError if crewai is not installed."""
        if importlib.util.find_spec("crewai") is None:
            raise ImportError(
                "crewai is not installed. Install it with: pip install binex[crewai]"
            )
        return CrewAIAdapter(uri, config)
