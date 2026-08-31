"""Resolving a reference run, whichever of the two eval systems named it.

`binex eval bless` records `(suite, case) -> run_id`; `binex eval golden
--baseline` wants a run id. They describe the same thing — a stored reference
run — so a baseline blessed for a suite is addressable as a golden baseline
without looking the id up by hand.

The other direction already works: `binex eval bless --run <id>` blesses any run.
"""

from __future__ import annotations

from typing import Any, Protocol


class BaselineStore(Protocol):
    """The slice of the execution store this module needs."""

    async def get_baselines(self, suite_name: str) -> dict[str, str]:
        ...


class BaselineNotFoundError(ValueError):
    """Raised when a `suite:case` reference names nothing blessed."""


async def resolve_baseline(ref: str, exec_store: BaselineStore | Any) -> str:
    """Resolve a baseline reference to a run id.

    ``run_abc123``        — a run id, returned unchanged (no store access).
    ``suite:case``        — the run blessed for that case.

    The split is on the *first* colon, so a case id may itself contain colons.
    """
    if ":" not in ref:
        return ref

    suite_name, _, case_id = ref.partition(":")
    baselines = await exec_store.get_baselines(suite_name)
    run_id = baselines.get(case_id)
    if run_id is None:
        raise BaselineNotFoundError(
            f"No blessed baseline for case '{case_id}' in suite '{suite_name}'. "
            f"Run `binex eval bless <suite.yaml> --case {case_id}` first, "
            f"or pass a run id directly."
        )
    return run_id


__all__ = ["BaselineNotFoundError", "BaselineStore", "resolve_baseline"]
