"""LLMAdapter — direct LLM calls via litellm."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

import click
import litellm

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import CostRecord, ExecutionResult
from binex.models.task import TaskNode
from binex.tools import execute_tool_call, resolve_tools

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = 2  # seconds, doubles each attempt


class LLMAdapter:
    """Adapter for direct LLM calls without an agent server."""

    def __init__(
        self,
        model: str,
        prompt_template: str | None = None,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        workflow_dir: str | None = None,
    ) -> None:
        self._model = model
        self._prompt_template = prompt_template
        self._api_base = api_base
        self._api_key = api_key
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._workflow_dir = workflow_dir

    def _build_completion_kwargs(
        self, messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build kwargs dict for litellm.acompletion, including optional params."""
        kwargs: dict[str, Any] = {"model": self._model, "messages": messages}
        optional = {
            "api_base": self._api_base,
            "api_key": self._api_key,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        for key, value in optional.items():
            if value is not None:
                kwargs[key] = value
        return kwargs

    async def _run_tool_loop(
        self,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
        message: Any,
        resolved_tools: list[Any],
        max_rounds: int,
    ) -> tuple[Any, list[Any]]:
        """Execute the tool-calling loop. Returns (final_message, all_responses)."""
        all_responses: list[Any] = []
        rounds = 0

        while getattr(message, "tool_calls", None) and resolved_tools:
            rounds += 1
            if rounds > max_rounds:
                raise RuntimeError(f"Exceeded max tool rounds ({max_rounds})")

            messages.append(message.model_dump())

            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    arguments = {}

                matching = [t for t in resolved_tools if t.name == func_name]
                if matching:
                    result = await execute_tool_call(matching[0], arguments)
                else:
                    result = f"Error: Unknown tool '{func_name}'"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            kwargs["messages"] = messages
            response = await self._completion_with_retry(**kwargs)
            message = response.choices[0].message
            all_responses.append(response)

        return message, all_responses

    @staticmethod
    def _accumulate_cost(
        responses: list[Any], task: TaskNode, model: str,
    ) -> CostRecord:
        """Calculate total cost from a list of LLM responses."""
        total_cost = 0.0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        source = "llm_tokens"
        has_usage = False

        for resp in responses:
            usage = getattr(resp, "usage", None)
            if usage:
                has_usage = True
                total_prompt_tokens += getattr(usage, "prompt_tokens", None) or 0
                total_completion_tokens += getattr(usage, "completion_tokens", None) or 0
                try:
                    total_cost += litellm.completion_cost(completion_response=resp)
                except Exception:
                    source = "llm_tokens_unavailable"

        if not has_usage:
            source = "llm_tokens_unavailable"

        return CostRecord(
            id=f"cost_{uuid.uuid4().hex[:12]}",
            run_id=task.run_id,
            task_id=task.node_id,
            cost=total_cost,
            source=source,
            prompt_tokens=total_prompt_tokens if has_usage else None,
            completion_tokens=total_completion_tokens if has_usage else None,
            model=model,
        )

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> ExecutionResult:
        prompt = self._build_prompt(task, input_artifacts)

        messages: list[dict[str, Any]] = []
        if task.system_prompt:
            messages.append({"role": "system", "content": task.system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = self._build_completion_kwargs(messages)

        # Tool calling setup
        max_tool_rounds = task.config.get("max_tool_rounds", 10)
        resolved_tools: list[Any] = []
        if task.tools and max_tool_rounds > 0:
            resolved_tools = resolve_tools(task.tools, workflow_dir=self._workflow_dir)
            kwargs["tools"] = [t.to_openai_schema() for t in resolved_tools]

        response = await self._completion_with_retry(**kwargs)
        message = response.choices[0].message
        all_responses = [response]

        # Run tool-calling loop if needed
        if getattr(message, "tool_calls", None) and resolved_tools:
            message, extra_responses = await self._run_tool_loop(
                messages, kwargs, message, resolved_tools, max_tool_rounds,
            )
            all_responses.extend(extra_responses)

        artifacts = [
            Artifact(
                id=f"art_{uuid.uuid4().hex[:12]}",
                run_id=task.run_id,
                type="llm_response",
                content=message.content,
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in input_artifacts],
                ),
            )
        ]

        cost_record = self._accumulate_cost(all_responses, task, self._model)
        return ExecutionResult(artifacts=artifacts, cost=cost_record)

    @staticmethod
    async def _completion_with_retry(**kwargs: Any) -> Any:
        """Call litellm.acompletion with exponential backoff retry."""
        for attempt in range(MAX_RETRIES):
            try:
                return await litellm.acompletion(**kwargs)
            except Exception as exc:
                is_last = attempt == MAX_RETRIES - 1
                if is_last:
                    raise
                wait = RETRY_BACKOFF * (2 ** attempt)
                msg = (
                    f"LLM call failed (attempt {attempt + 1}/{MAX_RETRIES}): "
                    f"{exc}. Retrying in {wait}s..."
                )
                logger.warning(msg)
                click.echo(click.style(f"  ⚠ {msg}", fg="yellow"))
                await asyncio.sleep(wait)
        # unreachable, but satisfies type checker
        raise RuntimeError("Retry loop exited unexpectedly")

    def _build_prompt(self, task: TaskNode, input_artifacts: list[Artifact]) -> str:
        if self._prompt_template:
            return self._prompt_template

        parts: list[str] = []
        if task.inputs:
            for key, value in task.inputs.items():
                # Skip unresolved ${node.output} references
                if isinstance(value, str) and "${" in value:
                    continue
                parts.append(f"{key}: {value}")
        for art in input_artifacts:
            if art.type == "feedback":
                parts.append(
                    f"\nYour previous output was rejected. "
                    f"Please revise based on this feedback:\n{art.content}"
                )
            else:
                parts.append(f"\nInput ({art.type}):\n{art.content}")
        return "\n".join(parts) if parts else "No input provided."

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE
