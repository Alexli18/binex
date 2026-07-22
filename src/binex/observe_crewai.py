"""CrewAI attribution for observer mode (#73).

Observer mode captures every LiteLLM call (see ``observer.py``). That alone gives
per-call costs and payloads, but the calls are a flat list — you can't see which
*task* or *agent* made each one. This module adds that attribution, and it does
so the way the design demands: **LiteLLM captures, CrewAI callbacks only attribute.**

CrewAI executes each task through ``Agent.execute_task``. We wrap that method so
that, for the duration of a task's execution, a context variable holds the
current ``(task, agent)`` identity. The LiteLLM logger reads that variable when a
call fires and tags the captured call with it. On flush, calls are grouped into a
parent *task node* (``crewai://<role>``) with each call as a child record — so
``binex trace`` shows tasks with their agent's calls nested underneath, and
``binex diff`` aligns two observed runs by task name (the "pseudo-spec").

**Guest safety.** We are patching someone else's library inside their process.
Every step is best-effort: if CrewAI isn't installed, or its API drifted so the
patch target is gone, we log a warning and fall back to the flat capture — we
never raise into the user's ``kickoff()``.
"""

from __future__ import annotations

import contextlib
import logging
import re
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Attribution:
    """Which CrewAI task/agent is executing right now."""

    task_key: str      # stable identity used for the node id (name-based)
    task_name: str     # human-readable task label
    agent_role: str    # the agent's role, e.g. "Senior Researcher"


# Async-task/thread-local: set while a CrewAI agent executes a task, read by the
# LiteLLM logger. Defaults to None (unattributed → flat capture).
_current: ContextVar[Attribution | None] = ContextVar(
    "binex_crewai_attribution", default=None,
)


def current_attribution() -> Attribution | None:
    """The task/agent executing on this call stack, or None if unattributed."""
    return _current.get()


def _slug(text: str) -> str:
    """A short, stable, filesystem/id-safe key from a task label."""
    s = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return (s or "task")[:48]


def _task_identity(task: object, index_hint: int) -> tuple[str, str]:
    """Return (task_key, task_name) for a CrewAI Task, resilient to API drift.

    Prefers an explicit ``task.name``; falls back to the description; finally to a
    positional key. The key is name-based so the same crew run twice aligns in
    ``binex diff``.
    """
    name = getattr(task, "name", None)
    if name:
        return _slug(str(name)), str(name)
    desc = getattr(task, "description", None)
    if desc:
        label = str(desc).strip().splitlines()[0][:60]
        return _slug(label), label
    return f"task_{index_hint:03d}", f"task {index_hint}"


def install_crewai_attribution() -> Callable[[], None]:
    """Patch CrewAI so LiteLLM calls are attributed to task/agent. Best-effort.

    Returns an uninstall callable that restores the original method. If CrewAI is
    absent or the expected method is missing, returns a no-op uninstaller after
    logging — observer capture still works, just without task/agent grouping.
    """
    try:
        from crewai.agent import Agent
    except Exception as exc:  # noqa: BLE001 — crewai optional / import churn
        logger.debug("observe: CrewAI not present, attribution disabled (%s)", exc)
        return lambda: None

    original = getattr(Agent, "execute_task", None)
    if original is None or not callable(original):
        logger.warning(
            "observe: crewai.Agent.execute_task not found — capturing calls "
            "without task/agent attribution (CrewAI version drift?)",
        )
        return lambda: None

    # A per-install counter for tasks we can't name, so positional keys are stable
    # within a run.
    state = {"n": 0}

    def wrapper(self: object, task: object, *args: object, **kwargs: object) -> object:
        token = None
        try:
            key, name = _task_identity(task, state["n"])
            state["n"] += 1
            role = str(getattr(self, "role", None) or "agent").strip()
            token = _current.set(Attribution(task_key=key, task_name=name, agent_role=role))
        except Exception as exc:  # noqa: BLE001 — attribution must never break execution
            logger.warning("observe: attribution setup failed: %s", exc)
        try:
            return original(self, task, *args, **kwargs)
        finally:
            if token is not None:
                with contextlib.suppress(Exception):
                    _current.reset(token)

    try:
        Agent.execute_task = wrapper
    except Exception as exc:  # noqa: BLE001
        logger.warning("observe: could not patch CrewAI for attribution: %s", exc)
        return lambda: None

    def uninstall() -> None:
        with contextlib.suppress(Exception):
            Agent.execute_task = original

    return uninstall


__all__ = ["Attribution", "current_attribution", "install_crewai_attribution"]
