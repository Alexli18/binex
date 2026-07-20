"""Node caching (issue #68): cache key, store, orchestrator reuse, clean."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from binex.adapters.local import LocalPythonAdapter
from binex.cli.clean import clean_cache_cmd
from binex.models.artifact import Artifact, Lineage
from binex.models.cache import CacheEntry
from binex.models.task import TaskNode
from binex.runtime.cache_key import compute_cache_key
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _task(**kw) -> TaskNode:
    base = dict(id="t", run_id="r", node_id="n", agent="llm://gpt-4o",
                system_prompt="do", inputs={}, config={}, tools=[])
    base.update(kw)
    return TaskNode(**base)


def _art(content, art_id="a1") -> Artifact:
    return Artifact(id=art_id, run_id="r", type="result", content=content,
                    lineage=Lineage(produced_by="up"))


# ── cache key ───────────────────────────────────────────────────────────

def test_cache_key_stable_for_same_inputs():
    t = _task()
    arts = [_art({"v": 1})]
    assert compute_cache_key(t, arts) == compute_cache_key(t, arts)


def test_cache_key_changes_with_prompt():
    arts = [_art({"v": 1})]
    assert compute_cache_key(_task(system_prompt="A"), arts) != \
           compute_cache_key(_task(system_prompt="B"), arts)


def test_cache_key_changes_with_input_content():
    t = _task()
    assert compute_cache_key(t, [_art({"v": 1})]) != \
           compute_cache_key(t, [_art({"v": 2})])


def test_cache_key_ignores_api_key():
    arts = [_art({"v": 1})]
    assert compute_cache_key(_task(config={"api_key": "sk-1"}), arts) == \
           compute_cache_key(_task(config={"api_key": "sk-2"}), arts)


# ── store roundtrip + clear ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_store_cache_roundtrip_and_clear():
    store = InMemoryExecutionStore()
    entry = CacheEntry(
        cache_key="k1", run_id="r1", node_id="n", artifact_ids=["a1"], saved_cost=0.5,
    )
    await store.put_cache_entry(entry)

    got = await store.get_cache_entry("k1")
    assert got is not None and got.saved_cost == 0.5
    assert await store.count_cache_entries() == 1

    cleared = await store.clear_cache_entries()
    assert cleared == 1
    assert await store.get_cache_entry("k1") is None


# ── orchestrator: cache hit across runs ─────────────────────────────────

def _cache_workflow() -> dict:
    return {
        "name": "cached",
        "nodes": {
            "a": {"agent": "local://track", "system_prompt": "x", "inputs": {},
                  "outputs": ["r"]},
            "b": {"agent": "local://track", "system_prompt": "y",
                  "inputs": {"d": "${a.r}"}, "outputs": ["r"], "depends_on": ["a"]},
        },
    }


def _tracking_orch(exec_store, art_store, exec_counter, *, cache=False, offline=False):
    async def handler(task, inputs):
        exec_counter.append(task.node_id)
        return [Artifact(
            id=f"art_{task.node_id}_{task.run_id}", run_id=task.run_id,
            type="r", content={"n": task.node_id},
            lineage=Lineage(produced_by=task.node_id),
        )]

    orch = Orchestrator(
        artifact_store=art_store, execution_store=exec_store,
        cache=cache, offline=offline,
    )
    orch.dispatcher.register_adapter("local://track", LocalPythonAdapter(handler=handler))
    return orch


@pytest.mark.asyncio
async def test_second_run_reuses_cache():
    exec_store, art_store = InMemoryExecutionStore(), InMemoryArtifactStore()
    executed: list[str] = []

    orch1 = _tracking_orch(exec_store, art_store, executed, cache=True)
    s1 = await orch1.run_workflow(_cache_workflow())
    assert s1.status == "completed"
    assert sorted(executed) == ["a", "b"]  # first run executes both

    executed.clear()
    orch2 = _tracking_orch(exec_store, art_store, executed, cache=True)
    s2 = await orch2.run_workflow(_cache_workflow())
    assert s2.status == "completed"
    assert executed == []  # second run: both nodes served from cache

    # A $0 cache cost record exists for the reused run.
    costs = await exec_store.list_costs(s2.run_id)
    assert any(c.source == "cache" and c.cost == 0.0 for c in costs)


@pytest.mark.asyncio
async def test_per_node_cache_opt_in():
    exec_store, art_store = InMemoryExecutionStore(), InMemoryArtifactStore()
    executed: list[str] = []
    wf = _cache_workflow()
    wf["nodes"]["a"]["cache"] = True  # only 'a' opts in

    orch1 = _tracking_orch(exec_store, art_store, executed)  # run-level cache OFF
    await orch1.run_workflow(wf)
    executed.clear()

    orch2 = _tracking_orch(exec_store, art_store, executed)
    await orch2.run_workflow(wf)
    # 'a' is cached (per-node); 'b' re-executes (not opted in).
    assert "a" not in executed
    assert "b" in executed


@pytest.mark.asyncio
async def test_offline_miss_fails_node():
    exec_store, art_store = InMemoryExecutionStore(), InMemoryArtifactStore()
    executed: list[str] = []
    orch = _tracking_orch(exec_store, art_store, executed, cache=True, offline=True)
    summary = await orch.run_workflow(_cache_workflow())
    # No cache exists yet → offline mode fails the first node, nothing executes.
    assert summary.status == "failed"
    assert executed == []


# ── CLI clean ───────────────────────────────────────────────────────────

def _store_with_entries():
    async def _setup():
        store = InMemoryExecutionStore()
        for i in range(3):
            await store.put_cache_entry(CacheEntry(
                cache_key=f"k{i}", run_id="r", node_id="n", artifact_ids=[],
            ))
        return store
    return asyncio.run(_setup())


def test_clean_cache_dry_run_reports_without_deleting():
    store = _store_with_entries()
    with patch("binex.cli.clean._get_stores", return_value=(store, None)):
        result = CliRunner().invoke(clean_cache_cmd, ["--dry-run"])
    assert result.exit_code == 0
    assert "3 cache entries" in result.output


def test_clean_cache_clears():
    store = _store_with_entries()
    with patch("binex.cli.clean._get_stores", return_value=(store, None)):
        result = CliRunner().invoke(clean_cache_cmd, [])
    assert result.exit_code == 0
    assert "Cleared 3" in result.output
