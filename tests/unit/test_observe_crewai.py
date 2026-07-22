"""Unit tests for CrewAI attribution wiring (#73) — no real Crew needed."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from binex.observe_crewai import (
    _slug,
    _task_identity,
    current_attribution,
    install_crewai_attribution,
)


def test_slug_is_stable_and_id_safe() -> None:
    assert _slug("Research the Topic!") == "research_the_topic"
    assert _slug("") == "task"
    assert _slug("A" * 100) == "a" * 48  # bounded length


def test_task_identity_prefers_name_then_description() -> None:
    named = SimpleNamespace(name="Write Post", description="ignored")
    assert _task_identity(named, 0) == ("write_post", "Write Post")

    desc_only = SimpleNamespace(name=None, description="Research GPR\nmore detail")
    key, label = _task_identity(desc_only, 0)
    assert key == "research_gpr"
    assert label == "Research GPR"

    anon = SimpleNamespace(name=None, description=None)
    assert _task_identity(anon, 7) == ("task_007", "task 7")


def test_attribution_defaults_to_none() -> None:
    assert current_attribution() is None


def test_install_sets_and_resets_attribution(monkeypatch: pytest.MonkeyPatch) -> None:
    crewai_agent = pytest.importorskip("crewai.agent")
    Agent = crewai_agent.Agent  # noqa: N806 — mirrors the real class name

    seen: dict[str, object] = {}

    # Stand in for the real execute_task: record what attribution is visible.
    def probe(self: object, task: object, *a: object, **k: object) -> str:
        attr = current_attribution()
        seen["role"] = attr.agent_role if attr else None
        seen["task_key"] = attr.task_key if attr else None
        return "ok"

    monkeypatch.setattr(Agent, "execute_task", probe)

    uninstall = install_crewai_attribution()
    try:
        fake_self = SimpleNamespace(role="Researcher")
        fake_task = SimpleNamespace(name="research", description=None)
        result = Agent.execute_task(fake_self, fake_task)
        assert result == "ok"
        assert seen == {"role": "Researcher", "task_key": "research"}
        # Context is reset after the call returns.
        assert current_attribution() is None
    finally:
        uninstall()

    # After uninstall the original (probe) is restored.
    assert Agent.execute_task is probe


def test_attribution_never_raises_without_crewai(monkeypatch: pytest.MonkeyPatch) -> None:
    """If crewai import fails, install degrades to a no-op uninstaller."""
    import builtins

    real_import = builtins.__import__

    def blocked_import(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("crewai"):
            raise ImportError("crewai not installed (simulated)")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    uninstall = install_crewai_attribution()  # must not raise
    uninstall()  # no-op, must not raise
