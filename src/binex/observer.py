"""Observer mode — debug an existing CrewAI (or any LiteLLM) run in place (#73).

The `crewai://` adapter asks users to move their Crew *inside* a Binex workflow.
Observer mode instead watches an existing run without migration — two lines in
the user's own code::

    from binex import observe

    with observe("my-crew-run"):
        crew.kickoff()

Interception is at the **LiteLLM** layer (not CrewAI callbacks): a custom logger
captures the full raw request (messages, model, params) and response of every
call, with exact token/cost accounting from the source. The observed run lands
in the normal `.binex` store — trace, per-call costs, artifacts, and diff —
viewable in `binex debug` / `binex ui`, marked `observed`.

This is the validation-gate prototype for #73: it proves the hook and the cost
breakdown. Per-agent/task attribution via CrewAI callbacks, and single-call
replay (#74), build on top once the approach is validated.

**Safety — we are a guest in someone else's process:** every internal error is
swallowed into a log warning; `observe()` must never crash the user's run.
"""

from __future__ import annotations

import contextlib
import logging
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CapturedCall:
    """One LiteLLM call captured during an observed run."""

    model: str
    messages: list[dict[str, Any]]
    response_text: str
    prompt_tokens: int | None
    completion_tokens: int | None
    cost: float | None
    latency_ms: int
    error: str | None = None


@dataclass
class _Capture:
    """Mutable collector shared with the LiteLLM logger."""

    calls: list[CapturedCall] = field(default_factory=list)


def _extract_response_text(response_obj: Any) -> str:
    try:
        return str(response_obj.choices[0].message.content or "")
    except Exception:
        return ""


def _extract_usage(response_obj: Any) -> tuple[int | None, int | None]:
    usage = getattr(response_obj, "usage", None)
    if not usage:
        return None, None
    return (
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
    )


def _make_logger(capture: _Capture) -> Any:
    """Build a LiteLLM CustomLogger that appends to ``capture`` (fail-safe)."""
    from litellm.integrations.custom_logger import CustomLogger

    class _ObserverLogger(CustomLogger):  # type: ignore[misc]
        def log_success_event(
            self, kwargs: dict[str, Any], response_obj: Any,
            start_time: Any, end_time: Any,
        ) -> None:
            try:
                import litellm

                try:
                    cost = litellm.completion_cost(completion_response=response_obj)
                except Exception:
                    cost = None
                pt, ct = _extract_usage(response_obj)
                latency_ms = _duration_ms(start_time, end_time)
                capture.calls.append(CapturedCall(
                    model=str(kwargs.get("model", "unknown")),
                    messages=list(kwargs.get("messages", [])),
                    response_text=_extract_response_text(response_obj),
                    prompt_tokens=pt, completion_tokens=ct, cost=cost,
                    latency_ms=latency_ms,
                ))
            except Exception as exc:  # noqa: BLE001 — never crash the user's run
                logger.warning("observe: failed to capture a call: %s", exc)

        def log_failure_event(
            self, kwargs: dict[str, Any], response_obj: Any,
            start_time: Any, end_time: Any,
        ) -> None:
            try:
                capture.calls.append(CapturedCall(
                    model=str(kwargs.get("model", "unknown")),
                    messages=list(kwargs.get("messages", [])),
                    response_text="",
                    prompt_tokens=None, completion_tokens=None, cost=None,
                    latency_ms=_duration_ms(start_time, end_time),
                    error=str(kwargs.get("exception", "call failed")),
                ))
            except Exception as exc:  # noqa: BLE001
                logger.warning("observe: failed to capture a failure: %s", exc)

    return _ObserverLogger()


def _duration_ms(start_time: Any, end_time: Any) -> int:
    try:
        return max(0, int((end_time - start_time).total_seconds() * 1000))
    except Exception:
        return 0


@contextlib.contextmanager
def observe(run_name: str) -> Iterator[_Capture]:
    """Capture every LiteLLM call made inside the block into an observed run.

    Yields the live capture (mostly for tests); on exit, flushes the captured
    calls to the `.binex` store as an ``observed`` run. Any error in setup,
    teardown, or flush is logged, never raised.
    """
    import litellm

    capture = _Capture()
    obs_logger = _make_logger(capture)
    previous = list(getattr(litellm, "callbacks", []) or [])
    try:
        litellm.callbacks = [*previous, obs_logger]
    except Exception as exc:  # noqa: BLE001
        logger.warning("observe: could not install LiteLLM callback: %s", exc)

    try:
        yield capture
    finally:
        with contextlib.suppress(Exception):
            litellm.callbacks = previous
        try:
            _flush_sync(run_name, capture.calls)
        except Exception as exc:  # noqa: BLE001 — flushing must not crash the user
            logger.warning("observe: failed to persist observed run: %s", exc)


def _flush_sync(run_name: str, calls: list[CapturedCall]) -> str | None:
    """Persist captured calls as an observed run. Returns the run_id."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(flush_observed_run(run_name, calls))
    # Already inside an event loop (rare for crew.kickoff()): run on a new loop
    # in a worker thread so we don't clash with the caller's loop.
    import threading

    result: dict[str, str | None] = {}

    def _worker() -> None:
        result["run_id"] = asyncio.run(flush_observed_run(run_name, calls))

    t = threading.Thread(target=_worker)
    t.start()
    t.join()
    return result.get("run_id")


async def flush_observed_run(
    run_name: str, calls: list[CapturedCall],
) -> str:
    """Write captured calls into the store as one observed run. Returns run_id."""
    from binex.cli import get_stores
    from binex.models.artifact import Artifact, Lineage
    from binex.models.cost import CostRecord
    from binex.models.execution import ExecutionRecord, RunSummary
    from binex.models.task import TaskStatus

    run_id = f"obs_{uuid.uuid4().hex[:12]}"
    trace_id = f"trace_{uuid.uuid4().hex[:12]}"
    exec_store, art_store = get_stores()
    try:
        now = datetime.now(UTC)
        failed = sum(1 for c in calls if c.error)
        await exec_store.create_run(RunSummary(
            run_id=run_id, workflow_name=run_name,
            status="failed" if failed and failed == len(calls) else "completed",
            started_at=now, completed_at=now,
            total_nodes=len(calls),
            completed_nodes=len(calls) - failed, failed_nodes=failed,
            total_cost=sum(c.cost or 0.0 for c in calls),
            observed=True,
        ))
        for i, call in enumerate(calls):
            task_id = f"call_{i:03d}"
            out_refs: list[str] = []
            if call.response_text:
                art = Artifact(
                    id=f"art_{uuid.uuid4().hex[:12]}", run_id=run_id,
                    type="result", content=call.response_text,
                    lineage=Lineage(produced_by=task_id),
                )
                await art_store.store(art)
                out_refs.append(art.id)
            await exec_store.record(ExecutionRecord(
                id=f"rec_{uuid.uuid4().hex[:12]}", run_id=run_id, task_id=task_id,
                agent_id=f"litellm://{call.model}",
                status=TaskStatus.FAILED if call.error else TaskStatus.COMPLETED,
                output_artifact_refs=out_refs,
                prompt=_summarize_messages(call.messages),
                model=call.model, latency_ms=call.latency_ms,
                trace_id=trace_id, error=call.error,
            ))
            if call.cost is not None or call.prompt_tokens is not None:
                await exec_store.record_cost(CostRecord(
                    id=f"cost_{uuid.uuid4().hex[:12]}", run_id=run_id,
                    task_id=task_id, cost=call.cost or 0.0, source="llm_tokens",
                    prompt_tokens=call.prompt_tokens,
                    completion_tokens=call.completion_tokens, model=call.model,
                ))
        return run_id
    finally:
        await exec_store.close()


def _summarize_messages(messages: list[dict[str, Any]]) -> str:
    """A compact one-string view of the request messages for the trace."""
    parts = []
    for m in messages:
        role = m.get("role", "?")
        content = m.get("content", "")
        if isinstance(content, list):  # multimodal
            content = " ".join(
                p.get("text", "[media]") for p in content if isinstance(p, dict)
            )
        parts.append(f"[{role}] {str(content)[:500]}")
    return "\n".join(parts)


__all__ = ["CapturedCall", "flush_observed_run", "observe"]
