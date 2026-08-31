"""A blessed suite baseline and a golden run are the same thing — one reference run.

`binex eval bless` stores `(suite, case) -> run_id`; `binex eval golden
--baseline` takes a run id. Until now the two could not address each other, so a
baseline blessed for a suite had to be looked up by hand and pasted in.

`bless --run <id>` already covers the other direction: any run can become a
baseline.
"""

from __future__ import annotations

import pytest

from binex.eval.baselines import BaselineNotFoundError, resolve_baseline


class _Store:
    def __init__(self, baselines: dict[str, dict[str, str]]) -> None:
        self._baselines = baselines
        self.queried: list[str] = []

    async def get_baselines(self, suite_name: str) -> dict[str, str]:
        self.queried.append(suite_name)
        return self._baselines.get(suite_name, {})


@pytest.mark.asyncio
async def test_a_bare_run_id_passes_through_untouched():
    """The existing form must keep working without touching the store."""
    store = _Store({})

    assert await resolve_baseline("run_abc123", store) == "run_abc123"
    assert store.queried == []


@pytest.mark.asyncio
async def test_suite_and_case_resolve_to_the_blessed_run():
    store = _Store({"my-suite": {"happy-path": "run_blessed"}})

    resolved = await resolve_baseline("my-suite:happy-path", store)

    assert resolved == "run_blessed"
    assert store.queried == ["my-suite"]


@pytest.mark.asyncio
async def test_unknown_case_names_both_halves():
    store = _Store({"my-suite": {"happy-path": "run_blessed"}})

    with pytest.raises(BaselineNotFoundError) as excinfo:
        await resolve_baseline("my-suite:missing", store)

    message = str(excinfo.value)
    assert "my-suite" in message
    assert "missing" in message
    assert "bless" in message  # points at the command that would fix it


@pytest.mark.asyncio
async def test_unknown_suite_is_reported_too():
    store = _Store({})

    with pytest.raises(BaselineNotFoundError):
        await resolve_baseline("nope:case", store)


@pytest.mark.asyncio
async def test_a_run_id_containing_a_colon_is_still_treated_as_a_reference():
    """`suite:case` wins over an exotic run id — the split is deliberate."""
    store = _Store({"a": {"b": "run_x"}})

    assert await resolve_baseline("a:b", store) == "run_x"


@pytest.mark.asyncio
async def test_case_ids_may_contain_colons():
    """Only the first colon separates; the rest belongs to the case id."""
    store = _Store({"suite": {"group:case": "run_y"}})

    assert await resolve_baseline("suite:group:case", store) == "run_y"
