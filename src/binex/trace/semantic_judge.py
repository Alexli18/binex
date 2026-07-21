"""LLM judge + cost estimation for semantic diff (#71).

Binex spending the user's tokens is opt-in and never silent: the CLI shows an
estimated cost *before* any call. The judge runs at temperature 0 with a narrow
rubric and reports a per-question confidence, so a verdict is stable and
auditable rather than a coin-flip.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from binex.trace.semantic_diff import QUESTIONS, SemanticJudgeFn

logger = logging.getLogger(__name__)

# Roughly the size of one judge reply; used only for the pre-flight estimate.
_COMPLETION_TOKENS_PER_CALL = 160
_CHARS_PER_TOKEN = 4  # coarse fallback when the tokenizer is unavailable

_SYSTEM = (
    "You compare two versions (A and B) of an automated step's output and report "
    "whether specific aspects changed. Answer ONLY with a JSON object of the form:\n"
    '{"structure": {"changed": true/false, "confidence": "high|medium|low", '
    '"reason": "<short>"}, "facts": {...}, "tone_format": {...}}\n'
    "Be strict: 'changed' means a real difference in that aspect, not mere "
    "rewording. Keep reasons under 15 words."
)


def _build_user_prompt(content_a: str, content_b: str, max_chars: int) -> str:
    a = content_a[:max_chars]
    b = content_b[:max_chars]
    questions = "\n".join(f"- {q['key']}: {q['ask']}" for q in QUESTIONS)
    return (
        f"Questions:\n{questions}\n\n"
        f"=== A ===\n{a}\n\n=== B ===\n{b}\n\n"
        "Return the JSON object now."
    )


def count_tokens(model: str, text: str) -> int:
    """Best-effort token count for ``text`` on ``model`` (coarse fallback)."""
    try:
        import litellm

        return int(litellm.token_counter(model=model, text=text))
    except Exception:
        return max(1, len(text) // _CHARS_PER_TOKEN)


@dataclass
class CostEstimate:
    calls: int
    prompt_tokens: int
    completion_tokens: int
    cost: float | None  # None when the model is unpriced

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def estimate_cost(
    pairs: list[tuple[str, str, str]], model: str, *, max_chars: int = 6000,
) -> CostEstimate:
    """Estimate the token/dollar cost of judging every changed pair."""
    from binex.cost_simulation import price_tokens

    prompt_tokens = 0
    for _node, a, b in pairs:
        prompt = _SYSTEM + _build_user_prompt(a, b, max_chars)
        prompt_tokens += count_tokens(model, prompt)
    completion_tokens = len(pairs) * _COMPLETION_TOKENS_PER_CALL
    cost = price_tokens(model, prompt_tokens, completion_tokens)
    return CostEstimate(
        calls=len(pairs),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost=cost,
    )


def make_semantic_judge(
    model: str, *, max_chars: int = 6000,
) -> SemanticJudgeFn:
    """Build a temperature-0 judge that answers the narrow rubric questions.

    Any error (or unparseable reply) yields an empty answer dict, which the
    analysis layer treats conservatively (assumes the aspect changed).
    """

    async def _judge(content_a: str, content_b: str) -> dict[str, dict[str, Any]]:
        import litellm

        from binex.runtime.json_repair import repair_json_text

        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _build_user_prompt(content_a, content_b, max_chars)},
        ]
        try:
            resp = await litellm.acompletion(
                model=model, messages=messages, temperature=0,
            )
            reply = resp["choices"][0]["message"]["content"] or ""
        except Exception as exc:  # noqa: BLE001 — never crash the diff
            logger.warning("semantic judge call failed (%s): %s", model, exc)
            return {}

        repaired = repair_json_text(reply)
        if repaired is None:
            logger.warning("semantic judge reply was not JSON: %r", reply[:120])
            return {}
        try:
            parsed = json.loads(repaired)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    return _judge


__all__ = [
    "CostEstimate",
    "count_tokens",
    "estimate_cost",
    "make_semantic_judge",
]
