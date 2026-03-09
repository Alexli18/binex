"""LLMAdapter — direct LLM calls via litellm."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

import click
import litellm

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = 2  # seconds, doubles each attempt

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.tools import execute_tool_call, resolve_tools


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

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> list[Artifact]:
        prompt = self._build_prompt(task, input_artifacts)

        messages: list[dict[str, Any]] = []
        if task.system_prompt:
            messages.append({"role": "system", "content": task.system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if self._api_base is not None:
            kwargs["api_base"] = self._api_base
        if self._api_key is not None:
            kwargs["api_key"] = self._api_key
        if self._temperature is not None:
            kwargs["temperature"] = self._temperature
        if self._max_tokens is not None:
            kwargs["max_tokens"] = self._max_tokens

        # Tool calling setup
        max_tool_rounds = task.config.get("max_tool_rounds", 10)

        resolved_tools: list[Any] = []
        if task.tools and max_tool_rounds > 0:
            resolved_tools = resolve_tools(task.tools, workflow_dir=self._workflow_dir)
            kwargs["tools"] = [t.to_openai_schema() for t in resolved_tools]

        response = await self._completion_with_retry(**kwargs)
        message = response.choices[0].message

        # Tool calling loop
        rounds = 0
        while getattr(message, "tool_calls", None) and resolved_tools:
            rounds += 1
            if rounds > max_tool_rounds:
                raise RuntimeError(
                    f"Exceeded max tool rounds ({max_tool_rounds})"
                )

            # Append assistant message with tool calls
            messages.append(message.model_dump())

            # Execute each tool call
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    arguments = {}

                # Find matching tool definition
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

            # Re-call with updated messages
            kwargs["messages"] = messages
            response = await self._completion_with_retry(**kwargs)
            message = response.choices[0].message

        content = message.content

        return [
            Artifact(
                id=f"art_{uuid.uuid4().hex[:12]}",
                run_id=task.run_id,
                type="llm_response",
                content=content,
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in input_artifacts],
                ),
            )
        ]

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
                msg = f"LLM call failed (attempt {attempt + 1}/{MAX_RETRIES}): {exc}. Retrying in {wait}s..."
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
            parts.append(f"\nInput ({art.type}):\n{art.content}")
        return "\n".join(parts) if parts else "No input provided."

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE
