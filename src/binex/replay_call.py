"""Stateless replay of a captured LLM call from an observed run (#74).

Because observer mode (#73) captures the *complete* request (messages, model),
any single call can be replayed statelessly — all of the framework's memory and
context are already baked into the captured messages, so nothing needs
reconstructing. Swap the model and/or edit the prompt, re-send, and diff the new
response against the original.

Boundaries (deliberate):
- **Stops at tool use.** If the replayed model requests a tool call, we show the
  requested tool + arguments but never execute it (implementations live in the
  user's environment).
- **No downstream continuation.** The result is a comparison artifact — it does
  not feed back into the observed pipeline.
- **Experimentation spend.** The replay's cost is recorded with source
  ``replay`` and excluded from run-level cost aggregation by default.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


class ReplayError(Exception):
    """The call could not be located or replayed."""


@dataclass
class ToolRequest:
    name: str
    arguments: str


@dataclass
class ReplayResult:
    run_id: str
    call_id: str
    original_model: str
    replay_model: str
    original_response: str
    replay_response: str
    cost: float | None
    tool_requests: list[ToolRequest] = field(default_factory=list)
    replay_artifact_id: str | None = None

    @property
    def changed(self) -> bool:
        return self.original_response.strip() != self.replay_response.strip()


def _extract_tool_requests(message: Any) -> list[ToolRequest]:
    out: list[ToolRequest] = []
    for tc in getattr(message, "tool_calls", None) or []:
        fn = getattr(tc, "function", None)
        if fn is not None:
            out.append(ToolRequest(
                name=getattr(fn, "name", "?"),
                arguments=str(getattr(fn, "arguments", "")),
            ))
    return out


async def _load_call(
    exec_store: Any, art_store: Any, run_id: str, call_id: str,
) -> tuple[dict[str, Any], str]:
    """Return (request_envelope, original_response_text) for a captured call."""
    run = await exec_store.get_run(run_id)
    if run is None:
        raise ReplayError(f"run '{run_id}' not found")
    if not getattr(run, "observed", False):
        raise ReplayError(
            f"run '{run_id}' is not an observed run — call replay only applies "
            "to runs captured via observe()"
        )
    records = {r.task_id: r for r in await exec_store.list_records(run_id)}
    rec = records.get(call_id)
    if rec is None:
        raise ReplayError(f"call '{call_id}' not found in run '{run_id}'")

    request: dict[str, Any] | None = None
    for ref in rec.input_artifact_refs:
        art = await art_store.get(ref)
        if art and isinstance(art.content, dict) and "messages" in art.content:
            request = art.content
            break
    if request is None:
        raise ReplayError(
            f"call '{call_id}' has no captured request to replay "
            "(was it captured before request-recording landed?)"
        )

    original = ""
    for ref in rec.output_artifact_refs:
        art = await art_store.get(ref)
        if art is not None:
            original = str(art.content)
            break
    return request, original


def _apply_overrides(
    request: dict[str, Any], model: str | None, prompt: str | None,
) -> tuple[str, list[dict[str, Any]]]:
    """Resolve the (model, messages) to send, applying user overrides."""
    use_model = model or request["model"]
    messages = [dict(m) for m in request["messages"]]
    if prompt is not None:
        # Replace the last user turn's content (or append one).
        for m in reversed(messages):
            if m.get("role") == "user":
                m["content"] = prompt
                break
        else:
            messages.append({"role": "user", "content": prompt})
    return use_model, messages


async def replay_call(
    run_id: str,
    call_id: str,
    *,
    model: str | None = None,
    prompt: str | None = None,
    mock_response: str | None = None,
) -> ReplayResult:
    """Re-send a captured call (optionally with a new model/prompt) and diff it."""
    import litellm

    from binex.cli import get_stores
    from binex.models.artifact import Artifact, Lineage
    from binex.models.cost import CostRecord

    exec_store, art_store = get_stores()
    try:
        request, original = await _load_call(exec_store, art_store, run_id, call_id)
        use_model, messages = _apply_overrides(request, model, prompt)

        kwargs: dict[str, Any] = {"model": use_model, "messages": messages}
        if mock_response is not None:
            kwargs["mock_response"] = mock_response
        response = await litellm.acompletion(**kwargs)

        message = response.choices[0].message
        replay_text = str(getattr(message, "content", "") or "")
        tool_requests = _extract_tool_requests(message)
        try:
            cost: float | None = litellm.completion_cost(completion_response=response)
        except Exception:
            cost = None

        # Store the replay result as a comparison artifact (experimentation).
        art = Artifact(
            id=f"art_{uuid.uuid4().hex[:12]}", run_id=run_id,
            type="replay",
            content=replay_text,
            metadata={
                "replay_of": call_id, "replay_model": use_model,
                "experimentation": True,
            },
            lineage=Lineage(produced_by=f"{call_id}::replay"),
        )
        await art_store.store(art)
        if cost is not None:
            await exec_store.record_cost(CostRecord(
                id=f"cost_{uuid.uuid4().hex[:12]}", run_id=run_id,
                task_id=f"{call_id}::replay", cost=cost, source="replay",
                model=use_model,
            ))

        return ReplayResult(
            run_id=run_id, call_id=call_id,
            original_model=str(request["model"]), replay_model=use_model,
            original_response=original, replay_response=replay_text,
            cost=cost, tool_requests=tool_requests, replay_artifact_id=art.id,
        )
    finally:
        await exec_store.close()


__all__ = ["ReplayError", "ReplayResult", "ToolRequest", "replay_call"]
