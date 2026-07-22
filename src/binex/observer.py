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
from collections.abc import Callable, Iterator
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
    # CrewAI attribution (None when the call was not made inside a CrewAI task —
    # e.g. a plain LiteLLM run or observe-demo). See observe_crewai.py.
    task_key: str | None = None
    task_name: str | None = None
    agent_role: str | None = None


@dataclass
class _Capture:
    """Mutable collector shared with the LiteLLM logger."""

    calls: list[CapturedCall] = field(default_factory=list)
    run_id: str | None = None  # set to the observed run's id after flush


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


def _build_success_call(
    kwargs: dict[str, Any], response_obj: Any, latency_ms: int,
) -> CapturedCall:
    """Build a CapturedCall for a successful LiteLLM call (with attribution/cost)."""
    import litellm

    try:
        cost = litellm.completion_cost(completion_response=response_obj)
    except Exception:
        cost = None
    pt, ct = _extract_usage(response_obj)
    attr = _current_attribution()
    return CapturedCall(
        model=str(kwargs.get("model", "unknown")),
        messages=list(kwargs.get("messages", [])),
        response_text=_extract_response_text(response_obj),
        prompt_tokens=pt, completion_tokens=ct, cost=cost,
        latency_ms=latency_ms,
        task_key=attr.task_key if attr else None,
        task_name=attr.task_name if attr else None,
        agent_role=attr.agent_role if attr else None,
    )


def _build_failure_call(
    kwargs: dict[str, Any], latency_ms: int, error: str,
) -> CapturedCall:
    """Build a CapturedCall for a failed LiteLLM call (with attribution)."""
    attr = _current_attribution()
    return CapturedCall(
        model=str(kwargs.get("model", "unknown")),
        messages=list(kwargs.get("messages", [])),
        response_text="",
        prompt_tokens=None, completion_tokens=None, cost=None,
        latency_ms=latency_ms, error=error,
        task_key=attr.task_key if attr else None,
        task_name=attr.task_name if attr else None,
        agent_role=attr.agent_role if attr else None,
    )


def _make_logger(capture: _Capture) -> Any:
    """Build a LiteLLM CustomLogger that appends to ``capture`` (fail-safe).

    Retained as a supported capture path (and covered by unit tests); ``observe``
    itself intercepts at the function level (see ``_install_litellm_capture``)
    because CrewAI replaces ``litellm.callbacks`` mid-run, which would silently
    drop a callback-based observer.
    """
    from litellm.integrations.custom_logger import CustomLogger

    class _ObserverLogger(CustomLogger):  # type: ignore[misc]
        def log_success_event(
            self, kwargs: dict[str, Any], response_obj: Any,
            start_time: Any, end_time: Any,
        ) -> None:
            try:
                capture.calls.append(_build_success_call(
                    kwargs, response_obj, _duration_ms(start_time, end_time),
                ))
            except Exception as exc:  # noqa: BLE001 — never crash the user's run
                logger.warning("observe: failed to capture a call: %s", exc)

        def log_failure_event(
            self, kwargs: dict[str, Any], response_obj: Any,
            start_time: Any, end_time: Any,
        ) -> None:
            try:
                capture.calls.append(_build_failure_call(
                    kwargs, _duration_ms(start_time, end_time),
                    str(kwargs.get("exception", "call failed")),
                ))
            except Exception as exc:  # noqa: BLE001
                logger.warning("observe: failed to capture a failure: %s", exc)

    return _ObserverLogger()


def _install_litellm_capture(litellm_mod: Any, capture: _Capture) -> Callable[[], None]:
    """Wrap ``litellm.completion``/``acompletion`` to capture every call.

    Function-level interception is robust where a callback isn't: CrewAI assigns
    ``litellm.callbacks`` to its own handler on each call, so a callback-based
    observer is wiped after the first call. Wrapping the function survives that.
    Returns an uninstall callable that restores the originals.
    """
    import functools
    import time

    originals: dict[str, Any] = {}

    def _wrap_sync(name: str, fn: Any) -> Any:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                resp = fn(*args, **kwargs)
            except Exception as exc:
                err = str(exc)
                _safe_append(capture, lambda: _build_failure_call(
                    kwargs, _elapsed_ms(start), err))
                raise
            _safe_append(capture, lambda: _build_success_call(
                kwargs, resp, _elapsed_ms(start)))
            return resp
        return wrapper

    def _wrap_async(name: str, fn: Any) -> Any:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                resp = await fn(*args, **kwargs)
            except Exception as exc:
                err = str(exc)
                _safe_append(capture, lambda: _build_failure_call(
                    kwargs, _elapsed_ms(start), err))
                raise
            _safe_append(capture, lambda: _build_success_call(
                kwargs, resp, _elapsed_ms(start)))
            return resp
        return wrapper

    for name, wrapper_factory in (("completion", _wrap_sync), ("acompletion", _wrap_async)):
        fn = getattr(litellm_mod, name, None)
        if fn is None:
            continue
        originals[name] = fn
        with contextlib.suppress(Exception):
            setattr(litellm_mod, name, wrapper_factory(name, fn))

    def uninstall() -> None:
        for name, fn in originals.items():
            with contextlib.suppress(Exception):
                setattr(litellm_mod, name, fn)

    return uninstall


def _elapsed_ms(start_perf: float) -> int:
    import time

    return max(0, int((time.perf_counter() - start_perf) * 1000))


def _safe_append(capture: _Capture, build: Callable[[], CapturedCall]) -> None:
    """Append a built CapturedCall, swallowing any error (guest safety)."""
    try:
        capture.calls.append(build())
    except Exception as exc:  # noqa: BLE001 — never crash the user's run
        logger.warning("observe: failed to capture a call: %s", exc)


def _current_attribution() -> Any:
    """Current CrewAI task/agent, or None. Never raises (guest safety)."""
    try:
        from binex.observe_crewai import current_attribution

        return current_attribution()
    except Exception:  # noqa: BLE001
        return None


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
    # Intercept at the function level (not litellm.callbacks): CrewAI reassigns
    # litellm.callbacks to its own handler mid-run, which would drop a
    # callback-based observer after the first call.
    uninstall_capture: Callable[[], None] = lambda: None  # noqa: E731
    try:
        uninstall_capture = _install_litellm_capture(litellm, capture)
    except Exception as exc:  # noqa: BLE001
        logger.warning("observe: could not install LiteLLM capture: %s", exc)

    # Attribute captured calls to CrewAI tasks/agents (best-effort; a no-op when
    # CrewAI isn't in use). Falls back to a flat capture on any drift.
    uninstall_attribution: Callable[[], None] = lambda: None  # noqa: E731
    try:
        from binex.observe_crewai import install_crewai_attribution

        uninstall_attribution = install_crewai_attribution()
    except Exception as exc:  # noqa: BLE001
        logger.warning("observe: could not install CrewAI attribution: %s", exc)

    try:
        yield capture
    finally:
        with contextlib.suppress(Exception):
            uninstall_attribution()
        with contextlib.suppress(Exception):
            uninstall_capture()
        try:
            capture.run_id = _flush_sync(run_name, capture.calls)
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
    """Write captured calls into the store as one observed run. Returns run_id.

    When calls carry CrewAI attribution, they are grouped into a parent *task
    node* per task, with each call a child record under it (``parent_task_id``).
    Otherwise (plain LiteLLM / observe-demo) each call is a flat top-level node —
    the original prototype behavior, preserved for backward compatibility.
    """
    from binex.cli import get_stores
    from binex.models.execution import RunSummary

    run_id = f"obs_{uuid.uuid4().hex[:12]}"
    trace_id = f"trace_{uuid.uuid4().hex[:12]}"
    exec_store, art_store = get_stores()
    try:
        now = datetime.now(UTC)
        total_cost = sum(c.cost or 0.0 for c in calls)
        attributed = any(c.task_key for c in calls)

        if attributed:
            groups = _group_by_task(calls)
            failed_tasks = sum(1 for g in groups if all(c.error for c in g.calls))
            status = "failed" if failed_tasks and failed_tasks == len(groups) else "completed"
            await exec_store.create_run(RunSummary(
                run_id=run_id, workflow_name=run_name, status=status,
                started_at=now, completed_at=now,
                total_nodes=len(groups),
                completed_nodes=len(groups) - failed_tasks,
                failed_nodes=failed_tasks,
                total_cost=total_cost, observed=True,
            ))
            for g in groups:
                await _persist_task_group(
                    exec_store, art_store, run_id, trace_id, g,
                )
        else:
            failed = sum(1 for c in calls if c.error)
            await exec_store.create_run(RunSummary(
                run_id=run_id, workflow_name=run_name,
                status="failed" if failed and failed == len(calls) else "completed",
                started_at=now, completed_at=now,
                total_nodes=len(calls),
                completed_nodes=len(calls) - failed, failed_nodes=failed,
                total_cost=total_cost, observed=True,
            ))
            for i, call in enumerate(calls):
                await _persist_call(
                    exec_store, art_store, run_id, trace_id,
                    task_id=f"call_{i:03d}", parent_task_id=None,
                    agent_id=f"litellm://{call.model}", call=call,
                )
        return run_id
    finally:
        await exec_store.close()


@dataclass
class _TaskGroup:
    """Calls belonging to one CrewAI task, in call order."""

    key: str
    name: str
    agent_role: str
    calls: list[CapturedCall] = field(default_factory=list)


def _group_by_task(calls: list[CapturedCall]) -> list[_TaskGroup]:
    """Group attributed calls by task, preserving first-seen order.

    Unattributed calls (no ``task_key``) are bucketed under a synthetic
    ``untasked`` node so nothing is dropped.
    """
    groups: dict[str, _TaskGroup] = {}
    order: list[str] = []
    for call in calls:
        key = call.task_key or "untasked"
        if key not in groups:
            groups[key] = _TaskGroup(
                key=key,
                name=call.task_name or "untasked calls",
                agent_role=call.agent_role or "agent",
            )
            order.append(key)
        groups[key].calls.append(call)
    return [groups[k] for k in order]


async def _persist_task_group(
    exec_store: Any, art_store: Any, run_id: str, trace_id: str,
    group: _TaskGroup,
) -> None:
    """Write a parent task node plus one child record per call."""
    from binex.models.execution import ExecutionRecord
    from binex.models.task import TaskStatus

    parent_id = group.key
    agent_id = f"crewai://{group.agent_role}"
    group_failed = all(c.error for c in group.calls)
    total_latency = sum(c.latency_ms for c in group.calls)

    # Parent task node — a grouping node; per-call cost/artifacts live on children.
    await exec_store.record(ExecutionRecord(
        id=f"rec_{uuid.uuid4().hex[:12]}", run_id=run_id, task_id=parent_id,
        agent_id=agent_id,
        status=TaskStatus.FAILED if group_failed else TaskStatus.COMPLETED,
        prompt=group.name, latency_ms=total_latency, trace_id=trace_id,
    ))
    for i, call in enumerate(group.calls):
        await _persist_call(
            exec_store, art_store, run_id, trace_id,
            task_id=f"{parent_id}::call_{i:03d}", parent_task_id=parent_id,
            agent_id=agent_id, call=call,
        )


async def _persist_call(
    exec_store: Any, art_store: Any, run_id: str, trace_id: str,
    *, task_id: str, parent_task_id: str | None, agent_id: str,
    call: CapturedCall,
) -> None:
    """Persist one captured call: request + response artifacts, record, cost."""
    from binex.models.artifact import Artifact, Lineage
    from binex.models.cost import CostRecord
    from binex.models.execution import ExecutionRecord
    from binex.models.task import TaskStatus

    in_refs: list[str] = []
    # Persist the raw request so the call can be replayed statelessly (#74).
    req_art = Artifact(
        id=f"art_{uuid.uuid4().hex[:12]}", run_id=run_id, type="llm_request",
        content={"model": call.model, "messages": call.messages},
        lineage=Lineage(produced_by=task_id),
    )
    await art_store.store(req_art)
    in_refs.append(req_art.id)
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
        parent_task_id=parent_task_id, agent_id=agent_id,
        status=TaskStatus.FAILED if call.error else TaskStatus.COMPLETED,
        input_artifact_refs=in_refs, output_artifact_refs=out_refs,
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
