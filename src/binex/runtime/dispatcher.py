"""Task dispatcher — resolves adapters, handles retries and deadlines."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable

from binex.adapters.base import AgentAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import ExecutionResult
from binex.models.task import TaskNode
from binex.telemetry import get_tracer


class SchemaValidationError(Exception):
    """Raised when node output fails schema validation."""


class Dispatcher:
    """Dispatches tasks to the appropriate agent adapter with retry and timeout."""

    def __init__(self) -> None:
        self._adapters: dict[str, AgentAdapter] = {}

    def register_adapter(self, agent_key: str, adapter: AgentAdapter) -> None:
        self._adapters[agent_key] = adapter

    def get_adapter(self, agent_key: str) -> AgentAdapter:
        if agent_key not in self._adapters:
            raise KeyError(f"No adapter registered for '{agent_key}'")
        return self._adapters[agent_key]

    async def _call_adapter(
        self,
        adapter: AgentAdapter,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
        stream: bool,
        stream_callback: Callable[[str], None] | None,
    ) -> ExecutionResult | list[Artifact]:
        """Call adapter.execute, forwarding stream params for LLM adapters."""
        from binex.adapters.llm import LLMAdapter

        if stream and isinstance(adapter, LLMAdapter):
            return await adapter.execute(
                task, input_artifacts, trace_id,
                stream=stream, stream_callback=stream_callback,
            )
        return await adapter.execute(task, input_artifacts, trace_id)

    async def _attempt_dispatch(
        self,
        adapter: AgentAdapter,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
        stream: bool,
        stream_callback: Callable[[str], None] | None,
        output_schema: dict | None,
        attempt: int,
        max_retries: int,
    ) -> tuple[ExecutionResult | None, list[Artifact]]:
        """Execute a single dispatch attempt.

        Returns (result, updated_artifacts). Result is None if schema retry needed.
        """
        result = await self._execute_with_timeout(
            adapter, task, input_artifacts, trace_id,
            stream, stream_callback,
        )

        if output_schema and result.artifacts:
            retry_feedback = self._handle_schema_feedback(
                result, output_schema, task, attempt, max_retries,
            )
            if retry_feedback is not None:
                return None, list(input_artifacts) + [retry_feedback]

        return result, input_artifacts

    async def dispatch(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
        *,
        stream: bool = False,
        stream_callback: Callable[[str], None] | None = None,
    ) -> ExecutionResult:
        tracer = get_tracer()
        with tracer.start_as_current_span(f"binex.node.{task.node_id}") as span:
            span.set_attribute("node.id", task.node_id)
            span.set_attribute("node.agent", task.agent)
            try:
                result = await self._dispatch_inner(
                    task, input_artifacts, trace_id,
                    stream=stream, stream_callback=stream_callback,
                )
                span.set_attribute("node.status", "completed")
                return result
            except Exception as exc:
                span.set_attribute("node.status", "failed")
                span.record_exception(exc)
                raise

    async def _dispatch_inner(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
        *,
        stream: bool = False,
        stream_callback: Callable[[str], None] | None = None,
    ) -> ExecutionResult:
        adapter = self.get_adapter(task.agent)
        max_retries = task.retry_policy.max_retries if task.retry_policy else 1
        backoff = task.retry_policy.backoff if task.retry_policy else "exponential"
        last_error: Exception | None = None
        output_schema = task.config.get("output_schema")

        for attempt in range(1, max_retries + 1):
            try:
                result, input_artifacts = await self._attempt_dispatch(
                    adapter, task, input_artifacts, trace_id,
                    stream, stream_callback, output_schema,
                    attempt, max_retries,
                )
                if result is not None:
                    return result
                await asyncio.sleep(_backoff_delay(attempt, backoff))
            except (TimeoutError, SchemaValidationError):
                raise
            except Exception as exc:
                last_error = exc
                if attempt < max_retries:
                    await asyncio.sleep(_backoff_delay(attempt, backoff))

        raise last_error  # type: ignore[misc]

    def _handle_schema_feedback(
        self,
        result: ExecutionResult,
        output_schema: dict,
        task: TaskNode,
        attempt: int,
        max_retries: int,
    ) -> Artifact | None:
        """Validate result against output schema.

        Returns a feedback Artifact for retry, or None if valid.
        Raises SchemaValidationError on final attempt failure.
        """
        return _validate_schema(result, output_schema, task, attempt, max_retries)

    async def _execute_with_timeout(
        self,
        adapter: AgentAdapter,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
        stream: bool,
        stream_callback: Callable[[str], None] | None,
    ) -> ExecutionResult:
        """Execute adapter call with optional timeout, normalizing result type."""
        coro = self._call_adapter(
            adapter, task, input_artifacts, trace_id,
            stream, stream_callback,
        )
        if task.deadline_ms:
            result = await asyncio.wait_for(coro, timeout=task.deadline_ms / 1000.0)
        else:
            result = await coro

        if not isinstance(result, ExecutionResult):
            result = ExecutionResult(artifacts=result)
        return result


def _validate_schema(
    result: ExecutionResult,
    output_schema: dict,
    task: TaskNode,
    attempt: int,
    max_retries: int,
) -> Artifact | None:
    """Validate result against output schema.

    Returns a feedback Artifact for retry, or None if valid.
    Raises SchemaValidationError on final attempt failure.
    """
    from binex.runtime.schema_validator import validate_output

    content = result.artifacts[0].content
    validation = validate_output(content, output_schema)
    if validation.valid:
        return None

    error_msg = "; ".join(validation.errors)
    if attempt < max_retries:
        return Artifact(
            id=f"art_{uuid.uuid4().hex[:12]}",
            run_id=task.run_id,
            type="feedback",
            content=(
                f"Schema validation failed: {error_msg}. "
                f"Please fix your output to match the required schema."
            ),
            lineage=Lineage(produced_by="schema_validator"),
        )
    raise SchemaValidationError(
        f"Output schema validation failed after "
        f"{max_retries} attempts: {error_msg}"
    )


def _backoff_delay(attempt: int, strategy: str) -> float:
    if strategy == "exponential":
        return min(2 ** (attempt - 1) * 0.1, 10.0)
    return 0.1  # fixed
