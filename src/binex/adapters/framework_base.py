"""BaseFrameworkAdapter — shared logic for all framework adapters."""

from __future__ import annotations

import importlib
import json
from abc import ABC, abstractmethod
from typing import Any

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import ExecutionResult
from binex.models.task import TaskNode


class BaseFrameworkAdapter(ABC):
    """Abstract base for framework adapters (LangChain, CrewAI, AutoGen).

    Subclasses override _invoke, _validate, and _extract_output.
    """

    _prefix: str = ""

    def __init__(self, import_path: str, config: dict[str, Any]) -> None:
        self._import_path = import_path
        self._config = config
        self._obj: Any | None = None

    def _load_object(self) -> Any:
        """Lazy-import the user's object via dotted path. Caches after first call."""
        if self._obj is not None:
            return self._obj

        try:
            module_path, attr_name = self._import_path.rsplit(".", 1)
        except ValueError:
            raise RuntimeError(
                f"{self._prefix}://{self._import_path} failed: "
                f"expected dotted path like 'package.module.ClassName'"
            ) from None

        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise RuntimeError(
                f"{self._prefix}://{self._import_path} failed: "
                f"cannot import module '{module_path}': {exc}"
            ) from exc

        obj = getattr(module, attr_name, None)
        if obj is None:
            raise RuntimeError(
                f"{self._prefix}://{self._import_path} failed: "
                f"module '{module_path}' has no attribute '{attr_name}'"
            )

        self._validate(obj)
        self._obj = obj
        return self._obj

    def _prepare_input(self, artifacts: list[Artifact]) -> Any:
        """Map input artifacts to framework input."""
        if len(artifacts) == 0:
            return {}
        if len(artifacts) == 1:
            return artifacts[0].content
        return {a.id: a.content for a in artifacts}

    def _normalize_output(self, result: Any) -> str:
        """Convert framework output to string."""
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            return json.dumps(result)
        if result is None:
            return ""
        return str(result)

    def _build_result(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        content: str,
    ) -> ExecutionResult:
        """Create ExecutionResult with a single output artifact and lineage."""
        artifact = Artifact(
            id=f"{task.node_id}_output",
            run_id=task.run_id,
            type="text",
            content=content,
            lineage=Lineage(
                produced_by=task.node_id,
                derived_from=[a.id for a in input_artifacts],
            ),
        )
        return ExecutionResult(artifacts=[artifact], cost=None)

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> ExecutionResult:
        """Execute the framework object with given inputs."""
        obj = self._load_object()
        input_data = self._prepare_input(input_artifacts)
        try:
            raw_result = await self._invoke(obj, input_data)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"{self._prefix}://{self._import_path} failed: {exc}"
            ) from exc
        output = self._extract_output(raw_result)
        content = self._normalize_output(output)
        return self._build_result(task, input_artifacts, content)

    async def cancel(self, task_id: str) -> None:
        """No-op — framework objects don't support cancellation."""

    async def health(self) -> AgentHealth:
        """Always alive — framework objects are local."""
        return AgentHealth.ALIVE

    @abstractmethod
    async def _invoke(self, obj: Any, input_data: Any) -> Any:
        """Call the framework object. Subclasses implement async/sync dispatch."""
        ...

    @abstractmethod
    def _validate(self, obj: Any) -> None:
        """Validate that obj has the required framework methods."""
        ...

    @abstractmethod
    def _extract_output(self, result: Any) -> Any:
        """Extract output from framework-specific result type."""
        ...
