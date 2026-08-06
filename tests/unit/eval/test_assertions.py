"""Unit tests for assertion evaluation, the judge, and the model (issue #60)."""

from __future__ import annotations

import pytest

from binex.eval.assertions import evaluate_assertions, summarize_failures
from binex.eval.judge import parse_verdict, resolve_judge_model
from binex.models.assertion import Assertion


@pytest.mark.asyncio
async def test_content_checks_pass() -> None:
    assertions = [
        Assertion(contains="hello"),
        Assertion(lacks="error"),
        Assertion(matches=r"\d+"),
        Assertion(min_length=3),
        Assertion(max_length=100),
    ]
    outcomes = await evaluate_assertions(assertions, content="hello 42")
    assert all(o.passed for o in outcomes)
    assert summarize_failures(outcomes) == ""


@pytest.mark.asyncio
async def test_content_checks_fail() -> None:
    outcomes = await evaluate_assertions(
        [Assertion(contains="bye"), Assertion(lacks="hello")],
        content="hello world",
    )
    assert not outcomes[0].passed
    assert "does not contain" in outcomes[0].detail
    assert not outcomes[1].passed
    assert "forbidden" in outcomes[1].detail


@pytest.mark.asyncio
async def test_equals_check() -> None:
    ok = await evaluate_assertions([Assertion(equals="exact")], content="exact")
    assert ok[0].passed
    bad = await evaluate_assertions([Assertion(equals="exact")], content="other")
    assert not bad[0].passed


@pytest.mark.asyncio
async def test_metric_checks() -> None:
    outcomes = await evaluate_assertions(
        [Assertion(cost_max=0.01), Assertion(latency_max_ms=1000)],
        content="x", cost=0.05, latency_ms=2000,
    )
    assert not outcomes[0].passed
    assert "cost" in outcomes[0].detail
    assert not outcomes[1].passed
    assert "latency" in outcomes[1].detail


@pytest.mark.asyncio
async def test_non_string_content_is_stringified() -> None:
    outcomes = await evaluate_assertions(
        [Assertion(contains="msg")], content={"msg": "hi"},
    )
    assert outcomes[0].passed


@pytest.mark.asyncio
async def test_judge_pass_and_fail() -> None:
    async def judge(assertion: Assertion, content: str) -> tuple[bool, str]:
        return ("good" in content, "verdict")

    ok = await evaluate_assertions(
        [Assertion(judge="is it good?")], content="this is good",
        judge=judge,
    )
    assert ok[0].passed

    bad = await evaluate_assertions(
        [Assertion(judge="is it good?")], content="this is bad",
        judge=judge,
    )
    assert not bad[0].passed
    assert "judge rejected" in bad[0].detail


@pytest.mark.asyncio
async def test_judge_declared_but_missing_fails_closed() -> None:
    outcomes = await evaluate_assertions(
        [Assertion(judge="rubric")], content="anything", judge=None,
    )
    assert not outcomes[0].passed
    assert "no judge" in outcomes[0].detail


@pytest.mark.asyncio
async def test_content_failure_short_circuits_judge() -> None:
    called = False

    async def judge(assertion: Assertion, content: str) -> tuple[bool, str]:
        nonlocal called
        called = True
        return True, "ok"

    # contains fails first, so the judge must not be invoked.
    outcomes = await evaluate_assertions(
        [Assertion(contains="missing", judge="rubric")],
        content="present", judge=judge,
    )
    assert not outcomes[0].passed
    assert called is False


def test_parse_verdict() -> None:
    assert parse_verdict("PASS: ok") == (True, "ok")
    assert parse_verdict("FAIL: nope")[0] is False
    # Unparseable → fail closed.
    assert parse_verdict("hmm")[0] is False


def test_resolve_judge_model(monkeypatch: pytest.MonkeyPatch) -> None:
    assert resolve_judge_model("explicit") == "explicit"
    monkeypatch.setenv("BINEX_JUDGE_MODEL", "env-model")
    assert resolve_judge_model(None) == "env-model"


def test_empty_assertion_rejected() -> None:
    with pytest.raises(ValueError, match="at least one check"):
        Assertion()


def test_judge_model_requires_rubric() -> None:
    # judge_model alongside a real check but no rubric → specific error.
    with pytest.raises(ValueError, match="judge_model requires"):
        Assertion(contains="x", judge_model="gpt-4o")


def test_assertion_label() -> None:
    assert Assertion(name="my-check", contains="x").label() == "my-check"
    assert Assertion(contains="x").label() == "contains='x'"
    assert Assertion(judge="rubric").label() == "judge"
