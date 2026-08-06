"""Tests for observer mode — LiteLLM capture + observed-run persistence (#73)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from binex.observer import (
    CapturedCall,
    _make_logger,
    _summarize_messages,
    flush_observed_run,
    observe,
)


@pytest.fixture(autouse=True)
def _store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("BINEX_STORE_PATH", str(tmp_path / ".binex"))
    return tmp_path


def _fake_response(text: str, pt: int = 10, ct: int = 5) -> SimpleNamespace:
    msg = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=msg)
    usage = SimpleNamespace(prompt_tokens=pt, completion_tokens=ct)
    return SimpleNamespace(choices=[choice], usage=usage)


# -- capture ---------------------------------------------------------------

def test_logger_captures_success() -> None:
    from binex.observer import _Capture
    cap = _Capture()
    obs_logger = _make_logger(cap)
    from datetime import UTC, datetime
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    t1 = datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)  # +1s
    obs_logger.log_success_event(
        {"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
        _fake_response("hello"), t0, t1,
    )
    assert len(cap.calls) == 1
    call = cap.calls[0]
    assert call.model == "gpt-4o"
    assert call.response_text == "hello"
    assert call.prompt_tokens == 10
    assert call.latency_ms == 1000


def test_logger_never_raises_on_bad_input() -> None:
    from binex.observer import _Capture
    cap = _Capture()
    obs_logger = _make_logger(cap)
    # Garbage response object must not raise (guest-in-process safety).
    obs_logger.log_success_event({"model": "x"}, object(), None, None)
    assert cap.calls[0].response_text == ""  # degraded, not crashed


def test_logger_captures_failure() -> None:
    from binex.observer import _Capture
    cap = _Capture()
    obs_logger = _make_logger(cap)
    obs_logger.log_failure_event(
        {"model": "gpt-4o", "messages": [], "exception": "boom"},
        None, None, None,
    )
    assert cap.calls[0].error == "boom"


def test_summarize_messages_multimodal() -> None:
    text = _summarize_messages([
        {"role": "system", "content": "be nice"},
        {"role": "user", "content": [{"type": "text", "text": "look"}, {"foo": 1}]},
    ])
    assert "[system]" in text and "be nice" in text
    assert "look" in text


# -- flush / persistence ---------------------------------------------------

@pytest.mark.asyncio
async def test_flush_creates_observed_run() -> None:
    calls = [
        CapturedCall("gpt-4o", [{"role": "user", "content": "a"}], "resp-a",
                     10, 20, 0.003, 800),
        CapturedCall("gpt-4o-mini", [{"role": "user", "content": "b"}], "resp-b",
                     5, 5, 0.0004, 200),
    ]
    run_id = await flush_observed_run("crew-run", calls)
    assert run_id.startswith("obs_")

    from binex.cli import get_stores
    exec_store, art_store = get_stores()
    try:
        run = await exec_store.get_run(run_id)
        assert run.observed is True
        assert run.workflow_name == "crew-run"
        assert run.status == "completed"
        assert run.total_nodes == 2
        assert abs(run.total_cost - 0.0034) < 1e-9

        records = await exec_store.list_records(run_id)
        assert {r.task_id for r in records} == {"call_000", "call_001"}
        assert {r.model for r in records} == {"gpt-4o", "gpt-4o-mini"}

        costs = await exec_store.list_costs(run_id)
        assert len(costs) == 2

        arts = await art_store.list_by_run(run_id)
        responses = {a.content for a in arts if a.type == "result"}
        assert responses == {"resp-a", "resp-b"}
        # Each call also stored its raw request for replay (#74).
        requests = [a for a in arts if a.type == "llm_request"]
        assert len(requests) == 2
    finally:
        await exec_store.close()


@pytest.mark.asyncio
async def test_flush_all_failed_marks_run_failed() -> None:
    calls = [
        CapturedCall("gpt-4o", [], "", None, None, None, 100, error="rate limited"),
    ]
    run_id = await flush_observed_run("bad-run", calls)
    from binex.cli import get_stores
    exec_store, _ = get_stores()
    try:
        run = await exec_store.get_run(run_id)
        assert run.status == "failed"
        assert run.observed is True
    finally:
        await exec_store.close()


def test_observe_context_manager_wraps_and_restores_litellm() -> None:
    import litellm

    before = litellm.completion
    with observe("ctx-run") as cap:
        # observe() wraps litellm.completion for the duration of the block.
        assert litellm.completion is not before
        # Simulate a captured call inside the block.
        cap.calls.append(
            CapturedCall("gpt-4o", [{"role": "user", "content": "x"}], "y",
                         1, 1, 0.0, 10),
        )
    # Original restored after the block.
    assert litellm.completion is before


def test_observe_captures_direct_litellm_call_via_mock() -> None:
    """A plain litellm.completion(mock_response=...) inside observe() is captured."""
    import litellm

    with observe("direct-run") as cap:
        litellm.completion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hello"}],
            mock_response="hi there",
        )
    assert len(cap.calls) == 1
    assert cap.calls[0].response_text == "hi there"
    assert cap.calls[0].model == "gpt-4o-mini"


def test_observe_reexported_from_package() -> None:
    import binex
    assert binex.observe is observe


def test_observe_demo_command_offline() -> None:
    """`binex observe-demo` produces an observed run with no API calls."""
    from click.testing import CliRunner

    from binex.cli.observe_demo import observe_demo_cmd

    result = CliRunner().invoke(observe_demo_cmd, ["--name", "demo-run"])
    assert result.exit_code == 0
    assert "Captured 4 LLM call(s)" in result.output
    assert "observed run 'obs_" in result.output
    assert "binex debug obs_" in result.output


@pytest.mark.asyncio
async def test_observed_run_shows_in_debug() -> None:
    calls = [CapturedCall("gpt-4o", [{"role": "user", "content": "a"}], "r",
                          1, 1, 0.001, 10)]
    run_id = await flush_observed_run("dbg-run", calls)
    from binex.cli import get_stores
    from binex.trace.debug_report import build_debug_report, format_debug_report
    exec_store, art_store = get_stores()
    try:
        report = await build_debug_report(exec_store, art_store, run_id)
        assert report.observed is True
        assert "[observed]" in format_debug_report(report)
    finally:
        await exec_store.close()
