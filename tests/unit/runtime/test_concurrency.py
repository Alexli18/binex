"""Tests for concurrency limiting — src/binex/runtime/concurrency.py + orchestrator."""

from __future__ import annotations

import asyncio

import pytest

from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.runtime.concurrency import ConcurrencyLimiter, provider_of
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore

# --------------------------------------------------------------------------
# provider_of
# --------------------------------------------------------------------------

@pytest.mark.parametrize("agent,expected", [
    ("llm://openai/gpt-4o", "openai"),
    ("llm://ollama/llama3", "ollama"),
    ("llm://gpt-4o", "gpt-4o"),
    ("local://echo", "local"),
    ("a2a://host:8080/agent", "a2a"),
    ("human://approve", "human"),
])
def test_provider_of(agent: str, expected: str):
    assert provider_of(agent) == expected


# --------------------------------------------------------------------------
# ConcurrencyLimiter.from_spec
# --------------------------------------------------------------------------

def test_from_spec_int():
    limiter = ConcurrencyLimiter.from_spec(5, default_limit=8)
    assert limiter.global_limit == 5
    assert limiter.provider_limits == {}


def test_from_spec_dict_with_default():
    limiter = ConcurrencyLimiter.from_spec(
        {"default": 4, "openai": 2, "ollama": 1}, default_limit=8,
    )
    assert limiter.global_limit == 4
    assert limiter.provider_limits == {"openai": 2, "ollama": 1}


def test_from_spec_dict_without_default_falls_back():
    limiter = ConcurrencyLimiter.from_spec({"openai": 2}, default_limit=8)
    assert limiter.global_limit == 8
    assert limiter.provider_limits == {"openai": 2}


def test_from_spec_none_uses_default():
    limiter = ConcurrencyLimiter.from_spec(None, default_limit=8)
    assert limiter.global_limit == 8
    assert limiter.provider_limits == {}


# --------------------------------------------------------------------------
# Actual in-flight limiting
# --------------------------------------------------------------------------

async def _measure_peak(limiter: ConcurrencyLimiter, agents: list[str]) -> dict:
    """Run one slot() per agent concurrently; record peak concurrency overall
    and per provider."""
    state = {"active": 0, "peak": 0, "by_provider": {}, "prov_peak": {}}

    async def work(agent: str) -> None:
        provider = provider_of(agent)
        async with limiter.slot(agent):
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
            state["by_provider"][provider] = state["by_provider"].get(provider, 0) + 1
            state["prov_peak"][provider] = max(
                state["prov_peak"].get(provider, 0), state["by_provider"][provider],
            )
            await asyncio.sleep(0.02)
            state["active"] -= 1
            state["by_provider"][provider] -= 1

    await asyncio.gather(*(work(a) for a in agents))
    return state


@pytest.mark.asyncio
async def test_global_cap_limits_concurrency():
    limiter = ConcurrencyLimiter(2)
    state = await _measure_peak(limiter, ["llm://openai/gpt-4o"] * 10)
    assert state["peak"] <= 2


@pytest.mark.asyncio
async def test_per_provider_cap_limits_that_provider():
    limiter = ConcurrencyLimiter(10, {"ollama": 1})
    agents = ["llm://ollama/llama3"] * 5 + ["llm://openai/gpt-4o"] * 5
    state = await _measure_peak(limiter, agents)
    # Ollama held to 1 at a time; global cap (10) lets the rest run freely.
    assert state["prov_peak"]["ollama"] == 1
    assert state["peak"] <= 10


# --------------------------------------------------------------------------
# Orchestrator integration
# --------------------------------------------------------------------------

def _tracking_dispatcher_workflow(concurrency: int) -> tuple[dict, dict]:
    """Return (workflow_dict, shared_state) with 6 independent tracked nodes."""
    workflow = {
        "name": "fanout",
        "concurrency": concurrency,
        "nodes": {
            f"n{i}": {
                "agent": "local://track",
                "system_prompt": "work",
                "inputs": {},
                "outputs": ["r"],
            }
            for i in range(6)
        },
    }
    return workflow, {"active": 0, "peak": 0}


@pytest.mark.asyncio
async def test_orchestrator_respects_concurrency_field():
    workflow, state = _tracking_dispatcher_workflow(concurrency=2)

    async def handler(task, inputs):
        state["active"] += 1
        state["peak"] = max(state["peak"], state["active"])
        await asyncio.sleep(0.02)
        state["active"] -= 1
        return [Artifact(
            id=f"art_{task.node_id}_{task.run_id}", run_id=task.run_id,
            type="r", content={"ok": True},
            lineage=Lineage(produced_by=task.node_id),
        )]

    orch = Orchestrator(
        artifact_store=InMemoryArtifactStore(),
        execution_store=InMemoryExecutionStore(),
    )
    orch.dispatcher.register_adapter("local://track", LocalPythonAdapter(handler=handler))

    summary = await orch.run_workflow(workflow)

    assert summary.status == "completed"
    assert summary.completed_nodes == 6
    assert state["peak"] <= 2  # 6 ready nodes, but never more than 2 in flight
