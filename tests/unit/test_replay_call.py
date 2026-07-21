"""Tests for stateless single-call replay of observed runs (#74)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from binex.observer import CapturedCall, flush_observed_run
from binex.replay_call import ReplayError, replay_call


@pytest.fixture(autouse=True)
def _store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("BINEX_STORE_PATH", str(tmp_path / ".binex"))
    return tmp_path


async def _observed_run() -> str:
    calls = [
        CapturedCall("gpt-4o", [{"role": "user", "content": "plan the trip"}],
                     "Day 1: Rome", 10, 20, 0.003, 800),
        CapturedCall("gpt-4o-mini", [{"role": "user", "content": "summarize"}],
                     "Short summary", 5, 5, 0.0004, 200),
    ]
    return await flush_observed_run("crew-run", calls)


# -- happy path ------------------------------------------------------------

@pytest.mark.asyncio
async def test_replay_with_mock_response() -> None:
    run_id = await _observed_run()
    result = await replay_call(
        run_id, "call_000", mock_response="Day 1: Paris (revised)",
    )
    assert result.original_response == "Day 1: Rome"
    assert result.replay_response == "Day 1: Paris (revised)"
    assert result.changed is True
    assert result.original_model == "gpt-4o"
    assert result.replay_model == "gpt-4o"  # no swap


@pytest.mark.asyncio
async def test_replay_model_swap() -> None:
    run_id = await _observed_run()
    result = await replay_call(
        run_id, "call_001", model="claude-sonnet-4-20250514",
        mock_response="same",
    )
    assert result.replay_model == "claude-sonnet-4-20250514"
    assert result.original_model == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_replay_prompt_override_reaches_model(monkeypatch) -> None:
    run_id = await _observed_run()
    seen: dict = {}

    async def fake_acompletion(**kwargs):
        seen.update(kwargs)
        msg = SimpleNamespace(content="ok", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)

    import litellm
    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    await replay_call(run_id, "call_000", prompt="a brand new prompt")
    last_user = [m for m in seen["messages"] if m["role"] == "user"][-1]
    assert last_user["content"] == "a brand new prompt"


# -- tool-call boundary ----------------------------------------------------

@pytest.mark.asyncio
async def test_replay_stops_at_tool_use(monkeypatch) -> None:
    run_id = await _observed_run()

    async def fake_acompletion(**kwargs):
        tool_call = SimpleNamespace(
            function=SimpleNamespace(name="search", arguments='{"q": "rome"}'))
        msg = SimpleNamespace(content=None, tool_calls=[tool_call])
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)

    import litellm
    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    result = await replay_call(run_id, "call_000")
    # The requested tool is surfaced but NOT executed.
    assert len(result.tool_requests) == 1
    assert result.tool_requests[0].name == "search"
    assert "rome" in result.tool_requests[0].arguments


# -- cost isolation --------------------------------------------------------

@pytest.mark.asyncio
async def test_replay_cost_excluded_from_run_total() -> None:
    run_id = await _observed_run()
    from binex.cli import get_stores

    exec_store, _ = get_stores()
    try:
        before = (await exec_store.get_run_cost_summary(run_id)).total_cost
    finally:
        await exec_store.close()

    await replay_call(run_id, "call_000", mock_response="x")

    exec_store, _ = get_stores()
    try:
        after = (await exec_store.get_run_cost_summary(run_id)).total_cost
        costs = await exec_store.list_costs(run_id)
    finally:
        await exec_store.close()
    assert abs(after - before) < 1e-9  # replay did not change the run total
    assert any(c.source == "replay" for c in costs)  # but it was recorded


# -- errors ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_replay_unknown_call() -> None:
    run_id = await _observed_run()
    with pytest.raises(ReplayError, match="not found"):
        await replay_call(run_id, "call_999", mock_response="x")


@pytest.mark.asyncio
async def test_replay_unknown_run() -> None:
    with pytest.raises(ReplayError, match="not found"):
        await replay_call("obs_nope", "call_000", mock_response="x")


@pytest.mark.asyncio
async def test_replay_rejects_non_observed_run() -> None:
    from binex.cli import get_stores
    from binex.models.execution import RunSummary

    exec_store, _ = get_stores()
    try:
        await exec_store.create_run(RunSummary(
            run_id="run_normal", workflow_name="w", status="completed",
            total_nodes=1, observed=False,
        ))
    finally:
        await exec_store.close()
    with pytest.raises(ReplayError, match="not an observed run"):
        await replay_call("run_normal", "call_000", mock_response="x")


# -- CLI -------------------------------------------------------------------

def test_cli_replay_call_offline() -> None:
    import asyncio

    from click.testing import CliRunner

    from binex.cli.replay import replay_cmd

    run_id = asyncio.run(_observed_run())
    result = CliRunner().invoke(replay_cmd, [
        run_id, "--call", "call_000", "--model", "gpt-4o",
        "--mock-response", "a different plan",
    ])
    assert result.exit_code == 0
    assert "a different plan" in result.output
    assert "CHANGED" in result.output
    assert "experimentation" in result.output
