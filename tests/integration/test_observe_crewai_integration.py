"""Newcomer-path integration tests for observer mode (#73).

These exercise the *real* CrewAI library — a minimal Crew is constructed and run
through ``crew.kickoff()`` wrapped in ``observe()``. Only the LLM transport is
mocked (via LiteLLM's ``mock_response``, so no network / API key); CrewAI's task
scheduling, agent execution, and its own LiteLLM integration are all real. This
is the executable form of the acceptance criteria on issue #73.

CrewAI is a heavy optional dependency; the whole module skips when it is absent.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

crewai = pytest.importorskip("crewai")

# CrewAI's ReAct agent terminates a task when the model emits "Final Answer:".
_MOCK = "Thought: I now can give a great answer\nFinal Answer: Mocked answer for testing."


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean, offline, zero-config environment — the newcomer's machine."""
    monkeypatch.setenv("BINEX_STORE_PATH", str(tmp_path / ".binex"))  # store auto-inits
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")           # mock, never sent
    monkeypatch.setenv("CREWAI_TELEMETRY_OPT_OUT", "true")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")


def _mock_litellm(monkeypatch: pytest.MonkeyPatch, response: str = _MOCK) -> None:
    """Mock only the LLM transport: real litellm pipeline, canned answer."""
    import litellm

    real = litellm.completion

    def fake(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("mock_response", response)
        return real(*args, **kwargs)

    monkeypatch.setattr(litellm, "completion", fake)


def _build_crew(*, single: bool = False) -> Any:
    """A minimal but real Crew: one or two named tasks with distinct agents."""
    from crewai import Agent, Crew, Task

    researcher = Agent(
        role="Senior Researcher", goal="Find facts", backstory="An expert.",
        llm="gpt-4o-mini", allow_delegation=False, verbose=False, max_iter=3,
    )
    t_research = Task(
        description="Research the topic of ground-penetrating radar",
        expected_output="research notes", agent=researcher, name="research",
    )
    if single:
        return Crew(agents=[researcher], tasks=[t_research], memory=False, verbose=False)

    writer = Agent(
        role="Writer", goal="Write it up", backstory="A wordsmith.",
        llm="gpt-4o-mini", allow_delegation=False, verbose=False, max_iter=3,
    )
    t_write = Task(
        description="Write a short summary from the research",
        expected_output="a summary", agent=writer, name="write",
    )
    return Crew(
        agents=[researcher, writer], tasks=[t_research, t_write],
        memory=False, verbose=False,
    )


# ---------------------------------------------------------------------------
# The acceptance test: the newcomer path.
# ---------------------------------------------------------------------------

async def test_newcomer_path_attributes_crew_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pip install + two lines → a run with per-task trace, per-call costs, payloads."""
    _mock_litellm(monkeypatch)
    crew = _build_crew()

    from binex import observe

    # Step 2+3: the user's own script, unchanged except the two lines.
    with observe("newcomer-crew") as cap:
        crew.kickoff()

    run_id = cap.run_id
    assert run_id is not None and run_id.startswith("obs_")

    from binex.cli import get_stores

    exec_store, art_store = get_stores()
    try:
        # (a) a run record exists and is flagged observed
        run = await exec_store.get_run(run_id)
        assert run is not None
        assert run.observed is True
        assert run.status == "completed"

        records = await exec_store.list_records(run_id)
        by_id = {r.task_id: r for r in records}

        # (b) tasks are attributed: a parent node per CrewAI task, grouped by name
        assert "research" in by_id
        assert "write" in by_id
        assert by_id["research"].agent_id == "crewai://Senior Researcher"
        assert by_id["write"].agent_id == "crewai://Writer"

        # agent steps are subtasks of their task (parent_task_id)
        children = [r for r in records if r.parent_task_id == "research"]
        assert children, "expected at least one captured call under 'research'"
        assert all(r.agent_id == "crewai://Senior Researcher" for r in children)

        # (c) per-call cost records exist (one per captured call)
        costs = await exec_store.list_costs(run_id)
        assert len(costs) >= 2
        assert run.total_cost > 0

        # (d) captured request AND response payloads are stored as artifacts
        arts = await art_store.list_by_run(run_id)
        requests = [a for a in arts if a.type == "llm_request"]
        results = [a for a in arts if a.type == "result"]
        assert requests, "no captured request artifacts"
        assert results, "no captured response artifacts"
        # a request artifact carries the full replayable payload
        assert all(
            isinstance(a.content, dict) and "messages" in a.content and "model" in a.content
            for a in requests
        )
    finally:
        await exec_store.close()


async def test_observed_crew_call_is_replayable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A captured call from an observed Crew run can be replayed statelessly (#74)."""
    _mock_litellm(monkeypatch)
    crew = _build_crew(single=True)

    from binex import observe

    with observe("replay-crew") as cap:
        crew.kickoff()
    run_id = cap.run_id
    assert run_id is not None

    from binex.cli import get_stores

    exec_store, _ = get_stores()
    try:
        records = await exec_store.list_records(run_id)
    finally:
        await exec_store.close()

    # Pick a leaf call record (has a captured request), not the grouping node.
    call = next(r for r in records if r.parent_task_id is not None and r.input_artifact_refs)

    from binex.replay_call import replay_call

    result = await replay_call(
        run_id, call.task_id, mock_response="A different replayed answer.",
    )
    assert result.replay_response == "A different replayed answer."
    assert result.changed is True
    assert result.replay_artifact_id is not None


async def test_two_observed_runs_diff_by_task_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The name-based task ids (the 'pseudo-spec') let binex diff align two runs."""
    _mock_litellm(monkeypatch)

    from binex import observe

    with observe("run-a") as cap_a:
        _build_crew(single=True).kickoff()
    with observe("run-b") as cap_b:
        _build_crew(single=True).kickoff()

    from binex.cli import get_stores
    from binex.trace.diff import diff_runs

    exec_store, art_store = get_stores()
    try:
        result = await diff_runs(exec_store, art_store, cap_a.run_id, cap_b.run_id)
    finally:
        await exec_store.close()

    # The 'research' task node aligns across both runs (present in both, not
    # only-in-a / only-in-b) — i.e. diff matched them by name.
    task_ids = {s["task_id"] for s in result["steps"]}
    assert "research" in task_ids


async def test_crash_in_capture_does_not_break_kickoff(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failure inside the capture path degrades to a warning — kickoff still completes."""
    _mock_litellm(monkeypatch)

    # Inject a failure into the capture path.
    import binex.observer as observer_mod

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("capture exploded")

    monkeypatch.setattr(observer_mod, "_build_success_call", _boom)

    crew = _build_crew(single=True)
    from binex import observe

    with caplog.at_level(logging.WARNING, logger="binex.observer"):
        with observe("crashy-crew") as cap:
            output = crew.kickoff()  # must NOT raise

    # The user's run produced a result despite the broken observer.
    assert output is not None
    # We warned rather than crashing, and captured nothing.
    assert any("failed to capture" in r.message for r in caplog.records)
    assert cap.calls == []
