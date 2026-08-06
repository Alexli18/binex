"""Tests for the make_judge() LLM-call closure in eval/judge.py.

parse_verdict/resolve_judge_model are covered elsewhere; here we pin the
async judge itself with a mocked litellm.acompletion — including the
fail-closed contract: a broken judge must never green-light a regression.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from binex.eval.judge import make_judge
from binex.models.assertion import Assertion


def _llm_reply(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def _assertion(**kwargs) -> Assertion:
    defaults = dict(judge="output must mention cats")
    defaults.update(kwargs)
    return Assertion(**defaults)


@pytest.mark.asyncio
async def test_pass_reply_parsed():
    judge = make_judge()
    mock = AsyncMock(return_value=_llm_reply("PASS: mentions cats"))

    with patch("litellm.acompletion", mock):
        passed, reason = await judge(_assertion(), "cats are great")

    assert passed is True
    assert reason == "mentions cats"


@pytest.mark.asyncio
async def test_fail_reply_parsed():
    judge = make_judge()
    mock = AsyncMock(return_value=_llm_reply("FAIL: no cats found"))

    with patch("litellm.acompletion", mock):
        passed, reason = await judge(_assertion(), "dogs only")

    assert passed is False
    assert reason == "no cats found"


@pytest.mark.asyncio
async def test_llm_exception_fails_closed():
    judge = make_judge()
    mock = AsyncMock(side_effect=ConnectionError("api down"))

    with patch("litellm.acompletion", mock):
        passed, reason = await judge(_assertion(), "anything")

    assert passed is False
    assert "judge error" in reason
    assert "api down" in reason


@pytest.mark.asyncio
async def test_empty_reply_fails_closed():
    judge = make_judge()
    mock = AsyncMock(return_value=_llm_reply(None))

    with patch("litellm.acompletion", mock):
        passed, reason = await judge(_assertion(), "anything")

    assert passed is False
    assert "unparseable" in reason


@pytest.mark.asyncio
async def test_model_resolution_assertion_wins_over_default():
    judge = make_judge(default_model="default-model")
    mock = AsyncMock(return_value=_llm_reply("PASS: ok"))

    with patch("litellm.acompletion", mock):
        await judge(_assertion(judge_model="per-assertion-model"), "text")

    assert mock.await_args.kwargs["model"] == "per-assertion-model"


@pytest.mark.asyncio
async def test_output_truncated_to_max_chars():
    judge = make_judge()
    mock = AsyncMock(return_value=_llm_reply("PASS: ok"))
    long_output = "x" * 10_000

    with patch("litellm.acompletion", mock):
        await judge(_assertion(judge="rubric text"), long_output)

    user_msg = mock.await_args.kwargs["messages"][1]["content"]
    assert "rubric text" in user_msg
    assert "x" * 8000 in user_msg
    assert "x" * 8001 not in user_msg
