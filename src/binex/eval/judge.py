"""LLM-as-judge for assertions (issue #60).

A thin, dependency-light judge: given a rubric and a node's output, ask a model
to answer PASS or FAIL with a one-line reason. Isolated from
:mod:`binex.eval.node_assertions` (which stays pure) and injected as a ``JudgeFn``.
"""

from __future__ import annotations

import logging
import os

from binex.eval.node_assertions import JudgeFn
from binex.models.assertion import Assertion

logger = logging.getLogger(__name__)

DEFAULT_JUDGE_MODEL = "gpt-4o-mini"

_SYSTEM = (
    "You are a strict evaluation judge. Given a RUBRIC and the OUTPUT of an "
    "automated step, decide whether the output satisfies the rubric. Reply with "
    "a single line: 'PASS: <reason>' or 'FAIL: <reason>'. Be concise."
)

_MAX_OUTPUT_CHARS = 8000


def resolve_judge_model(model: str | None) -> str:
    """Pick the judge model: explicit > env override > default."""
    return model or os.environ.get("BINEX_JUDGE_MODEL") or DEFAULT_JUDGE_MODEL


def parse_verdict(text: str) -> tuple[bool, str]:
    """Parse a judge reply into (passed, reason). Ambiguous replies fail closed."""
    stripped = text.strip()
    lowered = stripped.lower()
    if lowered.startswith("pass"):
        return True, stripped[4:].lstrip(": ").strip() or "pass"
    if lowered.startswith("fail"):
        return False, stripped[4:].lstrip(": ").strip() or "fail"
    # No clear verdict: fail closed so a broken judge never green-lights a regression.
    return False, f"unparseable judge reply: {stripped[:120]!r}"


def make_judge(default_model: str | None = None) -> JudgeFn:
    """Build a ``JudgeFn``. The model is resolved per-assertion (``judge_model``),
    falling back to ``default_model``/env/default. Any judge error fails closed.
    """

    async def _judge(assertion: Assertion, content: str) -> tuple[bool, str]:
        import litellm

        resolved = resolve_judge_model(assertion.judge_model or default_model)
        rubric = assertion.judge or ""
        snippet = content[:_MAX_OUTPUT_CHARS]
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"RUBRIC:\n{rubric}\n\nOUTPUT:\n{snippet}"},
        ]
        try:
            resp = await litellm.acompletion(
                model=resolved, messages=messages, temperature=0,
            )
            reply = resp["choices"][0]["message"]["content"] or ""
        except Exception as exc:  # noqa: BLE001 — judge must never crash the run
            logger.warning("judge call failed (%s): %s", resolved, exc)
            return False, f"judge error: {exc}"
        return parse_verdict(reply)

    return _judge


__all__ = ["DEFAULT_JUDGE_MODEL", "make_judge", "parse_verdict", "resolve_judge_model"]
