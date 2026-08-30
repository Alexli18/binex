"""bisect must walk nodes in dependency order, not in store-insertion order.

"The first node where the runs diverge" is only meaningful along the DAG. The
walk used to follow the order execution records came back in, which for a
fan-out is the order the branches happened to finish — so which branch is
reported as the root cause depended on a race.
"""

from __future__ import annotations

from typing import Any

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.trace.bisect import bisect_report, find_divergence


async def _seed_diamond(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
    run_id: str,
    contents: dict[str, Any],
    *,
    record_order: list[str],
) -> None:
    """Diamond a -> {b, c} -> d, recorded in *record_order*.

    Edges are expressed through artifact refs, the way the runtime writes them,
    so the walk can recover the topology without the workflow file.
    """
    await exec_store.create_run(RunSummary(
        run_id=run_id, workflow_name="diamond", status="completed",
        total_nodes=4, completed_nodes=4,
    ))

    deps = {"a": [], "b": ["a"], "c": ["a"], "d": ["b", "c"]}
    for node in ("a", "b", "c", "d"):
        await art_store.store(Artifact(
            id=f"art_{run_id}_{node}", run_id=run_id, type="result",
            content=contents[node], lineage=Lineage(produced_by=node),
        ))

    for node in record_order:
        await exec_store.record(ExecutionRecord(
            id=f"rec_{run_id}_{node}", run_id=run_id, task_id=node,
            agent_id="local://echo", status=TaskStatus.COMPLETED,
            input_artifact_refs=[f"art_{run_id}_{d}" for d in deps[node]],
            output_artifact_refs=[f"art_{run_id}_{node}"],
            latency_ms=10, trace_id=f"trace_{run_id}",
        ))


def _contents(**overrides: str) -> dict[str, Any]:
    base = {"a": "alpha", "b": "beta", "c": "gamma", "d": "delta"}
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_upstream_divergence_wins_over_later_recorded_branch():
    """`a` diverges; it must be the answer even when recorded last."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    # Both `a` and `c` diverge, but `a` is upstream of everything.
    # The store hands `c` back first — a plausible completion order.
    await _seed_diamond(
        exec_store, art_store, "good", _contents(),
        record_order=["c", "d", "b", "a"],
    )
    await _seed_diamond(
        exec_store, art_store, "bad",
        _contents(a="ALPHA-CHANGED", c="GAMMA-CHANGED"),
        record_order=["c", "d", "b", "a"],
    )

    point = await find_divergence(exec_store, art_store, "good", "bad")

    assert point is not None
    assert point.node_id == "a"


@pytest.mark.asyncio
async def test_sibling_order_is_deterministic():
    """Two fan-out siblings both diverge — the answer must not depend on a race."""
    results = []
    for order in (["a", "b", "c", "d"], ["a", "c", "b", "d"]):
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        await _seed_diamond(
            exec_store, art_store, "good", _contents(), record_order=order,
        )
        await _seed_diamond(
            exec_store, art_store, "bad",
            _contents(b="BETA-CHANGED", c="GAMMA-CHANGED"),
            record_order=order,
        )
        point = await find_divergence(exec_store, art_store, "good", "bad")
        assert point is not None
        results.append(point.node_id)

    assert results[0] == results[1]


@pytest.mark.asyncio
async def test_node_map_is_in_dependency_order():
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    await _seed_diamond(
        exec_store, art_store, "good", _contents(),
        record_order=["d", "c", "b", "a"],
    )
    await _seed_diamond(
        exec_store, art_store, "bad", _contents(),
        record_order=["d", "b", "c", "a"],
    )

    report = await bisect_report(exec_store, art_store, "good", "bad")

    order = [nc.node_id for nc in report.node_map]
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


@pytest.mark.asyncio
async def test_nodes_without_recoverable_edges_are_ordered_deterministically():
    """No artifact refs means no topology to recover.

    Store order is a race there too, so the fallback is id order — stable across
    runs, which is what the report needs.
    """
    orders = []
    for record_order in (["zulu", "alpha", "mike"], ["mike", "zulu", "alpha"]):
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        for run_id in ("good", "bad"):
            await exec_store.create_run(RunSummary(
                run_id=run_id, workflow_name="flat", status="completed",
                total_nodes=3, completed_nodes=3,
            ))
            for node in record_order:
                await exec_store.record(ExecutionRecord(
                    id=f"rec_{run_id}_{node}", run_id=run_id, task_id=node,
                    agent_id="local://echo", status=TaskStatus.COMPLETED,
                    latency_ms=10, trace_id=f"trace_{run_id}",
                ))
        report = await bisect_report(exec_store, art_store, "good", "bad")
        orders.append([nc.node_id for nc in report.node_map])

    assert orders[0] == orders[1] == ["alpha", "mike", "zulu"]
