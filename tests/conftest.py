"""Shared test fixtures for Binex test suite."""

from __future__ import annotations

import threading
import time

import pytest

from binex.stores.backends.sqlite import SqliteExecutionStore

_seen_aiosqlite_threads: set[int] = set()


def _live_aiosqlite_threads() -> set[int]:
    import aiosqlite

    return {
        t.ident
        for t in threading.enumerate()
        if isinstance(t, aiosqlite.Connection) and t.is_alive() and t.ident is not None
    }


@pytest.fixture(autouse=True)
def _no_leaked_aiosqlite_connections():
    """Fail any test that leaves a live aiosqlite worker thread behind.

    An unclosed SqliteExecutionStore keeps a non-daemon aiosqlite.Connection
    thread alive, which silently hangs interpreter shutdown after the whole
    suite has passed. This guard turns that into an explicit failure naming
    the offending test. Use the `sqlite_store` fixture (or try/finally with
    `await store.close()`) to avoid it.
    """
    yield
    leaked = _live_aiosqlite_threads() - _seen_aiosqlite_threads
    if leaked:
        # close() joins the worker thread, but give a short grace period for
        # the join to land before declaring a leak.
        time.sleep(0.05)
        leaked = _live_aiosqlite_threads() - _seen_aiosqlite_threads
    if leaked:
        # Remember them so only the first offending test fails, not everyone after.
        _seen_aiosqlite_threads.update(leaked)
        pytest.fail(
            f"{len(leaked)} aiosqlite connection thread(s) leaked by this test — "
            "a SqliteExecutionStore was not closed (await store.close(), "
            "or use the sqlite_store fixture)"
        )


@pytest.fixture
async def sqlite_store(tmp_path):
    """SqliteExecutionStore backed by a temp file, closed on teardown.

    Prefer this over instantiating SqliteExecutionStore directly: an unclosed
    store leaves a live aiosqlite worker thread that hangs interpreter exit.
    """
    store = SqliteExecutionStore(str(tmp_path / "test.db"))
    await store.initialize()
    yield store
    await store.close()


@pytest.fixture
def sample_workflow_dict() -> dict:
    """Minimal 2-node workflow spec as a dict."""
    return {
        "name": "test-workflow",
        "description": "A simple test workflow",
        "nodes": {
            "producer": {
                "agent": "local://echo",
                "system_prompt": "produce",
                "inputs": {"data": "${user.input}"},
                "outputs": ["result"],
            },
            "consumer": {
                "agent": "local://echo",
                "system_prompt": "consume",
                "inputs": {"data": "${producer.result}"},
                "outputs": ["final"],
                "depends_on": ["producer"],
            },
        },
        "defaults": {
            "deadline_ms": 30000,
            "retry_policy": {"max_retries": 1, "backoff": "exponential"},
        },
    }


@pytest.fixture
def sample_research_workflow_dict() -> dict:
    """5-node research pipeline workflow spec as a dict."""
    return {
        "name": "research-pipeline",
        "description": "Multi-agent research pipeline",
        "nodes": {
            "planner": {
                "agent": "local://planner",
                "system_prompt": "planning.research",
                "inputs": {"query": "${user.query}"},
                "outputs": ["execution_plan"],
            },
            "researcher_1": {
                "agent": "local://researcher",
                "system_prompt": "research.search",
                "inputs": {
                    "plan": "${planner.execution_plan}",
                    "source": "arxiv",
                },
                "outputs": ["search_results"],
                "depends_on": ["planner"],
            },
            "researcher_2": {
                "agent": "local://researcher",
                "system_prompt": "research.search",
                "inputs": {
                    "plan": "${planner.execution_plan}",
                    "source": "google_scholar",
                },
                "outputs": ["search_results"],
                "depends_on": ["planner"],
            },
            "validator": {
                "agent": "local://validator",
                "system_prompt": "analysis.validate",
                "inputs": {
                    "results_1": "${researcher_1.search_results}",
                    "results_2": "${researcher_2.search_results}",
                },
                "outputs": ["validated_results"],
                "depends_on": ["researcher_1", "researcher_2"],
                "retry_policy": {"max_retries": 2, "backoff": "exponential"},
            },
            "summarizer": {
                "agent": "local://summarizer",
                "system_prompt": "analysis.summarize",
                "inputs": {"validated": "${validator.validated_results}"},
                "outputs": ["summary_report"],
                "depends_on": ["validator"],
                "deadline_ms": 60000,
            },
        },
        "defaults": {
            "deadline_ms": 120000,
            "retry_policy": {"max_retries": 1, "backoff": "exponential"},
        },
    }
