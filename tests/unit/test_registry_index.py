"""Tests for capability index and search module."""

from __future__ import annotations

from binex.models.agent import AgentHealth, AgentInfo
from binex.registry.index import CapabilityIndex

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _agent(
    agent_id: str,
    capabilities: list[str],
    health: AgentHealth = AgentHealth.ALIVE,
    latency_avg_ms: int = 0,
) -> AgentInfo:
    return AgentInfo(
        id=agent_id,
        endpoint=f"http://{agent_id}.example.com",
        name=agent_id,
        capabilities=capabilities,
        health=health,
        latency_avg_ms=latency_avg_ms,
    )


# ---------------------------------------------------------------------------
# add_agent
# ---------------------------------------------------------------------------


def test_add_agent_indexes_capabilities():
    store: dict[str, AgentInfo] = {}
    index = CapabilityIndex(store)

    agent = _agent("a1", ["summarize", "translate"])
    store[agent.id] = agent
    index.add_agent(agent)

    assert index.search("summarize") == [agent]
    assert index.search("translate") == [agent]


def test_add_agent_no_capabilities():
    store: dict[str, AgentInfo] = {}
    index = CapabilityIndex(store)

    agent = _agent("a1", [])
    store[agent.id] = agent
    index.add_agent(agent)

    # Agent with no capabilities should not appear in any search
    assert index.search("summarize") == []


# ---------------------------------------------------------------------------
# remove_agent
# ---------------------------------------------------------------------------


def test_remove_agent_clears_entries():
    store: dict[str, AgentInfo] = {}
    index = CapabilityIndex(store)

    agent = _agent("a1", ["summarize", "translate"])
    store[agent.id] = agent
    index.add_agent(agent)

    index.remove_agent("a1")

    assert index.search("summarize") == []
    assert index.search("translate") == []


def test_remove_nonexistent_agent_is_noop():
    store: dict[str, AgentInfo] = {}
    index = CapabilityIndex(store)

    # Should not raise
    index.remove_agent("does-not-exist")


# ---------------------------------------------------------------------------
# update_agent
# ---------------------------------------------------------------------------


def test_update_agent_reindexes_capabilities():
    store: dict[str, AgentInfo] = {}
    index = CapabilityIndex(store)

    agent_v1 = _agent("a1", ["summarize", "translate"])
    store[agent_v1.id] = agent_v1
    index.add_agent(agent_v1)

    # Agent changes capabilities
    agent_v2 = _agent("a1", ["translate", "classify"])
    store[agent_v2.id] = agent_v2
    index.update_agent(agent_v2)

    assert index.search("summarize") == []  # removed
    assert index.search("translate") == [agent_v2]  # kept
    assert index.search("classify") == [agent_v2]  # added


# ---------------------------------------------------------------------------
# search — ranking
# ---------------------------------------------------------------------------


def test_search_returns_empty_for_unknown_capability():
    store: dict[str, AgentInfo] = {}
    index = CapabilityIndex(store)

    assert index.search("nonexistent") == []


def test_search_ranks_by_health_then_latency():
    store: dict[str, AgentInfo] = {}
    index = CapabilityIndex(store)

    agents = [
        _agent("down1", ["cap"], AgentHealth.DOWN, latency_avg_ms=10),
        _agent("alive_slow", ["cap"], AgentHealth.ALIVE, latency_avg_ms=200),
        _agent("alive_fast", ["cap"], AgentHealth.ALIVE, latency_avg_ms=50),
        _agent("slow1", ["cap"], AgentHealth.SLOW, latency_avg_ms=100),
        _agent("degraded1", ["cap"], AgentHealth.DEGRADED, latency_avg_ms=5),
    ]

    for a in agents:
        store[a.id] = a
        index.add_agent(a)

    results = index.search("cap")

    assert len(results) == 5
    assert results[0].id == "alive_fast"
    assert results[1].id == "alive_slow"
    assert results[2].id == "slow1"
    assert results[3].id == "degraded1"
    assert results[4].id == "down1"


def test_health_ranking_order():
    """Verify: alive < slow < degraded < down."""
    store: dict[str, AgentInfo] = {}
    index = CapabilityIndex(store)

    agents = [
        _agent("d", ["x"], AgentHealth.DOWN, latency_avg_ms=0),
        _agent("a", ["x"], AgentHealth.ALIVE, latency_avg_ms=0),
        _agent("s", ["x"], AgentHealth.SLOW, latency_avg_ms=0),
        _agent("g", ["x"], AgentHealth.DEGRADED, latency_avg_ms=0),
    ]

    for a in agents:
        store[a.id] = a
        index.add_agent(a)

    results = index.search("x")
    ids = [r.id for r in results]
    assert ids == ["a", "s", "g", "d"]


# ---------------------------------------------------------------------------
# search_multi
# ---------------------------------------------------------------------------


def test_search_multi_returns_agents_with_all_capabilities():
    store: dict[str, AgentInfo] = {}
    index = CapabilityIndex(store)

    a1 = _agent("a1", ["summarize", "translate"])
    a2 = _agent("a2", ["summarize"])
    a3 = _agent("a3", ["summarize", "translate", "classify"])

    for a in [a1, a2, a3]:
        store[a.id] = a
        index.add_agent(a)

    results = index.search_multi(["summarize", "translate"])

    result_ids = {r.id for r in results}
    assert result_ids == {"a1", "a3"}
    assert "a2" not in result_ids


def test_search_multi_empty_capabilities_returns_empty():
    store: dict[str, AgentInfo] = {}
    index = CapabilityIndex(store)

    a1 = _agent("a1", ["summarize"])
    store[a1.id] = a1
    index.add_agent(a1)

    assert index.search_multi([]) == []


def test_search_multi_ranks_results():
    store: dict[str, AgentInfo] = {}
    index = CapabilityIndex(store)

    a1 = _agent("a1", ["cap_a", "cap_b"], AgentHealth.ALIVE, latency_avg_ms=100)
    a2 = _agent("a2", ["cap_a", "cap_b"], AgentHealth.ALIVE, latency_avg_ms=10)

    for a in [a1, a2]:
        store[a.id] = a
        index.add_agent(a)

    results = index.search_multi(["cap_a", "cap_b"])
    assert results[0].id == "a2"
    assert results[1].id == "a1"


def test_search_multi_no_match_returns_empty():
    store: dict[str, AgentInfo] = {}
    index = CapabilityIndex(store)

    a1 = _agent("a1", ["summarize"])
    store[a1.id] = a1
    index.add_agent(a1)

    assert index.search_multi(["summarize", "translate"]) == []
