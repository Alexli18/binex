"""LLMAdapter — direct LLM calls via litellm."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from typing import Any

import click
import litellm

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import CostRecord, CostSource, ExecutionResult
from binex.models.task import TaskNode
from binex.tools import execute_tool_call, resolve_tools

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = 2  # seconds, doubles each attempt


def _is_binary(artifact: Any) -> bool:
    """True if an artifact carries a binary envelope (#76)."""
    c = getattr(artifact, "content", None)
    return isinstance(c, dict) and c.get("kind") == "binary"


def _fallback_reason(exc: Exception) -> str | None:
    """Classify an exception as a fallback trigger, or None if not retriable.

    Fallback fires on infrastructure/availability failures only — never on a
    successful-but-bad response (that's repair territory, #65).
    """
    reasons = [
        ("RateLimitError", "rate_limited"),
        ("Timeout", "timeout"),
        ("APIConnectionError", "connection_error"),
        ("InternalServerError", "server_error"),
        ("ServiceUnavailableError", "server_error"),
        ("NotFoundError", "model_not_found"),
        ("AuthenticationError", "auth_error"),
    ]
    for cls_name, reason in reasons:
        exc_type = getattr(litellm, cls_name, None)
        if exc_type is not None and isinstance(exc, exc_type):
            return reason
    status = getattr(exc, "status_code", None)
    if status == 429:
        return "rate_limited"
    if status == 401:
        return "auth_error"
    if isinstance(status, int) and 500 <= status < 600:
        return "server_error"
    return None


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
        mcp_manager: Any | None = None,
    ) -> None:
        self._model = model
        self._prompt_template = prompt_template
        self._api_base = api_base
        self._api_key = api_key
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._workflow_dir = workflow_dir
        self._mcp_manager = mcp_manager

    @staticmethod
    def _is_mcp_placeholder(t: Any) -> bool:
        """Check if a tool is an MCP placeholder."""
        val = getattr(t, "_mcp_server", None)
        return isinstance(val, str)

    async def _expand_mcp_tools(
        self, tools: list[Any],
    ) -> list[Any]:
        """Expand MCP placeholder tools into actual tool definitions."""
        if self._mcp_manager is None:
            return [t for t in tools if not self._is_mcp_placeholder(t)]

        expanded: list[Any] = []
        for t in tools:
            if self._is_mcp_placeholder(t):
                server_name = t._mcp_server
                mcp_tools = await self._mcp_manager.get_tools(server_name)
                expanded.extend(mcp_tools)
            else:
                expanded.append(t)
        return expanded

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

    def _maybe_add_structured_output(
        self, kwargs: dict[str, Any], output_schema: dict[str, Any] | None,
    ) -> None:
        """Step 2: ask the provider for schema-conformant output when supported.

        Detected per-model; silently skipped where the provider doesn't support
        it, so malformed output mostly never happens in the first place.
        """
        if not output_schema:
            return
        try:
            supported = litellm.supports_response_schema(self._model)
        except Exception:
            supported = False
        if supported:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "schema": output_schema},
            }

    async def _repair_feedback_loop(
        self,
        messages: list[dict[str, Any]],
        base_kwargs: dict[str, Any],
        content: Any,
        output_schema: dict[str, Any],
        max_attempts: int,
    ) -> tuple[Any, list[Any], dict[str, Any] | None]:
        """Step 3: re-ask the model to fix schema-invalid output, in context.

        Returns (final_content, extra_responses, repair_metadata). Deterministic
        repair runs first (0 tokens); only genuinely invalid output triggers a
        model call. Every attempt's response is returned so its cost is counted.
        """
        from binex.runtime.schema_validator import validate_output

        extra_responses: list[Any] = []
        validation = validate_output(content, output_schema)
        if validation.valid:
            if validation.repaired and isinstance(content, str):
                return (
                    json.dumps(validation.normalized), extra_responses,
                    {"repair_attempts": 0, "repair_step": "deterministic"},
                )
            return content, extra_responses, None

        convo = [*messages, {"role": "assistant", "content": content}]
        for attempt in range(1, max_attempts + 1):
            errors = "; ".join(validation.errors)
            convo.append({
                "role": "user",
                "content": (
                    f"Your previous output failed schema validation: {errors}. "
                    "Return ONLY valid JSON matching the schema — no prose, no code fences."
                ),
            })
            kwargs = {**base_kwargs, "messages": convo}
            response = await self._completion_with_retry(**kwargs)
            extra_responses.append(response)
            content = response.choices[0].message.content
            convo.append({"role": "assistant", "content": content})

            validation = validate_output(content, output_schema)
            if validation.valid:
                final = (
                    json.dumps(validation.normalized)
                    if isinstance(content, str) else content
                )
                return final, extra_responses, {
                    "repair_attempts": attempt, "repair_step": "feedback",
                }

        return content, extra_responses, {
            "repair_attempts": max_attempts, "repair_step": "feedback",
            "repaired": False, "validation_errors": validation.errors,
        }

    async def _escalate_repair(
        self,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
        output_schema: dict[str, Any],
        repair_attempts: int,
        task: TaskNode,
        actual_model: str,
        all_responses: list[Any],
    ) -> tuple[Any, str, dict[str, Any]] | None:
        """On repair exhaustion, retry the repair ladder on later chain models.

        Returns (content, model, metadata) from the first model that repairs
        successfully — or the last model's result if all are exhausted. Returns
        None when there is nothing further to escalate to. ``BINEX_NO_FALLBACK``
        disables escalation, like ordinary fallback.
        """
        import os

        if os.environ.get("BINEX_NO_FALLBACK"):
            return None
        chain = [self._model, *(task.config.get("fallbacks") or [])]
        try:
            start = chain.index(actual_model) + 1
        except ValueError:
            return None
        if start >= len(chain):
            return None

        last: tuple[Any, str, dict[str, Any]] | None = None
        for model in chain[start:]:
            kwargs["model"] = model
            try:
                response = await self._completion_with_retry(**kwargs)
            except Exception as exc:
                # A transport error on an escalation target: skip to the next.
                if _fallback_reason(exc) is not None:
                    continue
                raise
            all_responses.append(response)
            content = response.choices[0].message.content
            content, extra, meta = await self._repair_feedback_loop(
                messages, kwargs, content, output_schema, repair_attempts,
            )
            all_responses.extend(extra)
            result_meta: dict[str, Any] = {
                **(meta or {}),
                "escalated": "schema_repair_exhausted",
                "escalated_to": model,
            }
            logger.warning(
                "Repair escalation: %s → %s (schema repair exhausted)",
                actual_model, model,
            )
            last = (content, model, result_meta)
            if not (meta and meta.get("repaired") is False):
                return last  # this model repaired successfully
        return last

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
        source: CostSource = "llm_tokens"
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

    async def _streaming_completion(
        self,
        kwargs: dict[str, Any],
        callback: Callable[[str], None] | None = None,
    ) -> tuple[Any, str]:
        """Call litellm with streaming, return (reconstructed_response, full_content)."""
        stream_kwargs = {**kwargs, "stream": True}
        chunks: list[Any] = []
        content_parts: list[str] = []

        response = await litellm.acompletion(**stream_kwargs)
        async for chunk in response:
            chunks.append(chunk)
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and getattr(delta, "content", None):
                token = delta.content
                content_parts.append(token)
                if callback:
                    callback(token)

        full_content = "".join(content_parts)
        # Rebuild response for cost calculation
        rebuilt = litellm.stream_chunk_builder(chunks)
        return rebuilt, full_content

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
        *,
        stream: bool = False,
        stream_callback: Callable[[str], None] | None = None,
    ) -> ExecutionResult:
        user_content = self._build_user_content(task, input_artifacts)

        messages: list[dict[str, Any]] = []
        if task.system_prompt:
            messages.append({"role": "system", "content": task.system_prompt})
        messages.append({"role": "user", "content": user_content})

        kwargs = self._build_completion_kwargs(messages)

        # Auto-repair setup (issue #65)
        output_schema = task.config.get("output_schema")
        repair_cfg = task.config.get("repair") or {}
        repair_attempts = int(repair_cfg.get("max_attempts", 0))
        self._maybe_add_structured_output(kwargs, output_schema)

        # Tool calling setup
        max_tool_rounds = task.config.get("max_tool_rounds", 10)
        resolved_tools: list[Any] = []
        if max_tool_rounds > 0:
            if task.tools:
                resolved_tools = resolve_tools(
                    task.tools,
                    workflow_dir=self._workflow_dir,
                    mcp_manager=self._mcp_manager,
                )
                # Expand MCP placeholders to actual tools
                resolved_tools = await self._expand_mcp_tools(resolved_tools)
            # Workspace file tools (#75): jailed to the run's workspace root.
            ws_root = task.config.get("_workspace_root")
            if ws_root:
                from pathlib import Path

                from binex.runtime.workspace import Workspace
                from binex.runtime.workspace_tools import make_workspace_tools
                resolved_tools = resolved_tools + make_workspace_tools(
                    Workspace(run_id="", root=Path(ws_root)),
                )
            if resolved_tools:
                kwargs["tools"] = [t.to_openai_schema() for t in resolved_tools]

        # Streaming mode (only for non-tool-calling initial request)
        if stream and not resolved_tools:
            try:
                response, content = await self._streaming_completion(kwargs, stream_callback)
                artifacts = [
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
                cost_record = self._accumulate_cost([response], task, self._model)
                return ExecutionResult(artifacts=artifacts, cost=cost_record)
            except Exception as exc:
                logger.warning("Streaming failed, falling back to non-streaming: %s", exc)

        # Non-streaming path, with model fallback (issue #66).
        response, actual_model, fallback_events = await self._complete_with_fallback(
            kwargs, task,
        )
        message = response.choices[0].message
        all_responses = [response]

        # Run tool-calling loop if needed
        used_tools = bool(getattr(message, "tool_calls", None) and resolved_tools)
        if used_tools:
            message, extra_responses = await self._run_tool_loop(
                messages, kwargs, message, resolved_tools, max_tool_rounds,
            )
            all_responses.extend(extra_responses)

        content = message.content
        repair_metadata: dict[str, Any] | None = None

        # Step 3: schema-repair feedback loop (structured-output nodes without tools).
        if output_schema and repair_attempts > 0 and not used_tools:
            content, repair_responses, repair_metadata = await self._repair_feedback_loop(
                messages, kwargs, content, output_schema, repair_attempts,
            )
            all_responses.extend(repair_responses)

            # Escalation (#67): repair exhausted on this model, and the node opted
            # in — promote to the next model in the fallback chain and retry the
            # repair ladder there. Trigger is "schema repair exhausted", distinct
            # from the transport-error fallback in _complete_with_fallback.
            if (
                repair_metadata and repair_metadata.get("repaired") is False
                and repair_cfg.get("escalate")
            ):
                escalated = await self._escalate_repair(
                    messages, kwargs, output_schema, repair_attempts,
                    task, actual_model, all_responses,
                )
                if escalated is not None:
                    content, actual_model, repair_metadata = escalated

        metadata: dict[str, Any] = dict(repair_metadata or {})
        metadata["requested_model"] = self._model
        metadata["actual_model"] = actual_model
        if fallback_events:
            metadata["fallbacks"] = fallback_events

        artifacts = [
            Artifact(
                id=f"art_{uuid.uuid4().hex[:12]}",
                run_id=task.run_id,
                type="llm_response",
                content=content,
                metadata=metadata,
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in input_artifacts],
                ),
            )
        ]

        cost_record = self._accumulate_cost(all_responses, task, actual_model)
        return ExecutionResult(artifacts=artifacts, cost=cost_record)

    async def _complete_with_fallback(
        self, kwargs: dict[str, Any], task: TaskNode,
    ) -> tuple[Any, str, list[dict[str, str]]]:
        """Try the primary model then each fallback, on infrastructure errors.

        Returns (response, actual_model, fallback_events). Fallback is triggered
        only by transport/availability failures (rate limit, 5xx, timeout,
        model-not-found, auth) — never by a model that answered but poorly (that
        is auto-repair's job, #65). ``BINEX_NO_FALLBACK`` disables the chain so
        benchmarks aren't silently contaminated.
        """
        import os

        fallbacks: list[str] = (
            [] if os.environ.get("BINEX_NO_FALLBACK")
            else list(task.config.get("fallbacks") or [])
        )
        models = [self._model, *fallbacks]
        events: list[dict[str, str]] = []
        last_exc: Exception | None = None

        for i, model in enumerate(models):
            kwargs["model"] = model
            try:
                return await self._completion_with_retry(**kwargs), model, events
            except Exception as exc:
                reason = _fallback_reason(exc)
                has_next = i + 1 < len(models)
                if has_next and reason is not None:
                    nxt = models[i + 1]
                    events.append({"from": model, "to": nxt, "reason": reason})
                    warn = f"Model fallback: {model} → {nxt} ({reason})"
                    if reason == "auth_error":
                        warn += " — WARNING: auth failure, trying a different provider"
                    logger.warning(warn)
                    click.echo(click.style(f"  ⚠ {warn}", fg="yellow"))
                    last_exc = exc
                    continue
                raise
        # Unreachable: the last model always either returns or re-raises above.
        raise last_exc if last_exc is not None else RuntimeError("no models to try")

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
            if _is_binary(art):
                # Binaries are routed by _build_user_content; a descriptor stands
                # in here so text-only prompt building stays correct.
                from binex.artifacts.binary import binary_descriptor
                parts.append(
                    "\n" + binary_descriptor(art.content, art.lineage.produced_by)
                )
            elif art.type == "feedback":
                parts.append(
                    f"\nYour previous output was rejected. "
                    f"Please revise based on this feedback:\n{art.content}"
                )
            else:
                parts.append(f"\nInput ({art.type}):\n{art.content}")
        return "\n".join(parts) if parts else "No input provided."

    def _build_user_content(
        self, task: TaskNode, input_artifacts: list[Artifact],
    ) -> str | list[dict[str, Any]]:
        """Build the user message content, routing binaries by mime type (#76).

        Images go into the message as image parts when the model supports vision
        (LiteLLM multimodal); otherwise (and for audio/video) a textual descriptor
        goes into the prompt so the payload still travels the DAG intact.
        """
        text = self._build_prompt(task, input_artifacts)
        image_parts: list[dict[str, Any]] = []

        has_image = any(
            _is_binary(a) and str(a.content.get("mime", "")).startswith("image/")
            for a in input_artifacts
        )
        vision = self._model_supports_vision()
        if has_image and not vision:
            logger.warning(
                "node '%s' receives an image but model '%s' lacks vision — "
                "passing it as a textual descriptor instead.",
                task.node_id, self._model,
            )

        if vision:
            from binex.artifacts.binary import to_data_uri
            for art in input_artifacts:
                env = art.content if _is_binary(art) else None
                if env and str(env.get("mime", "")).startswith("image/"):
                    try:
                        image_parts.append({
                            "type": "image_url",
                            "image_url": {"url": to_data_uri(env)},
                        })
                    except Exception as exc:  # noqa: BLE001 — fall back to descriptor
                        logger.warning("could not attach image artifact: %s", exc)

        if not image_parts:
            return text
        return [{"type": "text", "text": text}, *image_parts]

    def _model_supports_vision(self) -> bool:
        try:
            import litellm

            return bool(litellm.supports_vision(self._model))
        except Exception:
            return False

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE
