"""Tests for the MCP server wiring layer (server.py).

Handler logic is tested directly in test_mcp_server_tools.py; here we pin
the wrapper layer's two real failure modes:

- registration drift — a tool added to tools.py but never registered on the
  FastMCP instance;
- store leak — a wrapper that fails to close its store when the handler raises.

The stdio transport itself (``mcp.run()``) is a conscious testing boundary:
it is FastMCP's code, exercised only by a real MCP client end-to-end.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from binex.mcp_server import server
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore

EXPECTED_TOOLS = {
    "list_workflows",
    "run_workflow",
    "get_run_status",
    "list_runs",
    "debug_node",
    "diagnose_run",
    "diff_runs",
    "replay_node",
    "eval_run",
    "get_artifact",
}


class _ClosableExecStore(InMemoryExecutionStore):
    """In-memory store that records close() calls."""

    def __init__(self) -> None:
        super().__init__()
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1


WRAPPER_CALLS = [
    ("list_workflows", ()),
    ("run_workflow", ("wf.yaml",)),
    ("get_run_status", ("run-1",)),
    ("list_runs", ()),
    ("debug_node", ("run-1", "node-a")),
    ("diagnose_run", ("run-1",)),
    ("diff_runs", ("run-a", "run-b")),
    ("replay_node", ("run-1", "node-a")),
    ("eval_run", ("suite.yaml",)),
    ("get_artifact", ("art-1",)),
]


@pytest.mark.asyncio
async def test_all_ten_tools_registered():
    tools = await server.mcp.list_tools()

    assert {t.name for t in tools} == EXPECTED_TOOLS


@pytest.mark.parametrize(("tool_name", "args"), WRAPPER_CALLS)
@pytest.mark.asyncio
async def test_each_wrapper_delegates_to_its_handler_and_closes(tool_name, args):
    exec_store = _ClosableExecStore()
    art_store = InMemoryArtifactStore()
    sentinel = {"ok": tool_name}
    handler = AsyncMock(return_value=sentinel)

    with (
        patch.object(server, "_get_stores", return_value=(exec_store, art_store)),
        patch.object(server._t, tool_name, handler),
    ):
        result = await getattr(server, tool_name)(*args)

    assert result == sentinel
    assert handler.await_count == 1
    # stores are always the first two positional args of the tools.py handler
    assert handler.await_args.args[:2] == (exec_store, art_store)
    assert exec_store.close_calls == 1


@pytest.mark.asyncio
async def test_wrapper_delegates_to_handler_and_closes_store():
    exec_store = _ClosableExecStore()
    art_store = InMemoryArtifactStore()

    with patch.object(server, "_get_stores", return_value=(exec_store, art_store)):
        result = await server.get_run_status("nonexistent-run")

    assert result["code"] == "not_found"
    assert exec_store.close_calls == 1


@pytest.mark.asyncio
async def test_wrapper_closes_store_when_handler_raises():
    exec_store = _ClosableExecStore()
    art_store = InMemoryArtifactStore()

    with (
        patch.object(server, "_get_stores", return_value=(exec_store, art_store)),
        patch.object(
            server._t, "get_run_status", new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
        pytest.raises(RuntimeError, match="boom"),
    ):
        await server.get_run_status("run-x")

    assert exec_store.close_calls == 1


@pytest.mark.asyncio
async def test_wrapper_swallows_close_failure():
    exec_store = _ClosableExecStore()
    exec_store.close = AsyncMock(side_effect=OSError("already closed"))  # type: ignore[method-assign]
    art_store = InMemoryArtifactStore()

    with patch.object(server, "_get_stores", return_value=(exec_store, art_store)):
        result = await server.get_run_status("nonexistent-run")

    # A failing close() must not mask the handler's result
    assert result["code"] == "not_found"
