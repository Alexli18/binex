"""MCP server — exposes Binex workflow tools over the Model Context Protocol.

Transport: stdio (started by ``binex mcp serve``).
All logging goes to stderr so it does not interfere with the JSON-RPC framing
that FastMCP writes to stdout.
"""

from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

from binex.mcp_server import tools as _t

# ---------------------------------------------------------------------------
# Logging — stderr only
# ---------------------------------------------------------------------------

logging.basicConfig(
    stream=sys.stderr,
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
_log = logging.getLogger("binex.mcp_server")

# ---------------------------------------------------------------------------
# FastMCP instance
# ---------------------------------------------------------------------------

mcp = FastMCP("binex")

# ---------------------------------------------------------------------------
# Store factory (extracted for test patching)
# ---------------------------------------------------------------------------


def _get_stores() -> tuple:  # type: ignore[type-arg]
    """Return (exec_store, art_store) using the default CLI pattern."""
    from binex.cli import get_stores

    return get_stores()


# ---------------------------------------------------------------------------
# Tool registrations
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_workflows(base_dir: str | None = None) -> dict:  # type: ignore[type-arg]
    """Discover workflow YAML files in the current working directory or *base_dir*.

    Returns ``{"workflows": [{"path", "name", "description?"}]}``.
    """
    exec_store, art_store = _get_stores()
    try:
        return await _t.list_workflows(exec_store, art_store, base_dir=base_dir)
    finally:
        try:
            await exec_store.close()
        except Exception:  # noqa: BLE001
            pass


@mcp.tool()
async def run_workflow(path: str, inputs: dict | None = None) -> dict:  # type: ignore[type-arg]
    """Run a workflow to completion with optional scripted inputs.

    Args:
        path: Relative or absolute path to the workflow YAML file.
        inputs: Key/value pairs for ``human://`` nodes (scripted input).

    Returns ``{"run_id", "status", "completed_nodes", "failed_nodes", "total_cost"}``.
    """
    exec_store, art_store = _get_stores()
    try:
        return await _t.run_workflow(exec_store, art_store, path, inputs=inputs)
    finally:
        try:
            await exec_store.close()
        except Exception:  # noqa: BLE001
            pass


@mcp.tool()
async def get_run_status(run_id: str) -> dict:  # type: ignore[type-arg]
    """Return the current status of a workflow run.

    Returns run summary fields: ``run_id``, ``status``, ``completed_nodes``, etc.
    """
    exec_store, art_store = _get_stores()
    try:
        return await _t.get_run_status(exec_store, art_store, run_id)
    finally:
        try:
            await exec_store.close()
        except Exception:  # noqa: BLE001
            pass


@mcp.tool()
async def list_runs(limit: int = 10) -> dict:  # type: ignore[type-arg]
    """List the most recent workflow runs.

    Args:
        limit: Maximum number of runs to return (default 10).

    Returns ``{"runs": [<run status shape>, ...]}``.
    """
    exec_store, art_store = _get_stores()
    try:
        return await _t.list_runs(exec_store, art_store, limit=limit)
    finally:
        try:
            await exec_store.close()
        except Exception:  # noqa: BLE001
            pass


@mcp.tool()
async def debug_node(run_id: str, node_id: str) -> dict:  # type: ignore[type-arg]
    """Return debug information for a specific node execution.

    Includes inputs/outputs (truncated at 4 000 chars), prompt, cost, and error.
    Use ``get_artifact`` for full untruncated artifact content.
    """
    exec_store, art_store = _get_stores()
    try:
        return await _t.debug_node(exec_store, art_store, run_id, node_id)
    finally:
        try:
            await exec_store.close()
        except Exception:  # noqa: BLE001
            pass


@mcp.tool()
async def diagnose_run(run_id: str) -> dict:  # type: ignore[type-arg]
    """Diagnose a workflow run and return a structured report.

    Reuses the same diagnostic logic as ``binex diagnose``.
    """
    exec_store, art_store = _get_stores()
    try:
        return await _t.diagnose_run(exec_store, art_store, run_id)
    finally:
        try:
            await exec_store.close()
        except Exception:  # noqa: BLE001
            pass


@mcp.tool()
async def diff_runs(run_id_a: str, run_id_b: str) -> dict:  # type: ignore[type-arg]
    """Diff two workflow runs and return a comparison report.

    Reuses the same diff logic as ``binex diff``.  String values in the report
    are truncated at 4 000 chars.
    """
    exec_store, art_store = _get_stores()
    try:
        return await _t.diff_runs(exec_store, art_store, run_id_a, run_id_b)
    finally:
        try:
            await exec_store.close()
        except Exception:  # noqa: BLE001
            pass


@mcp.tool()
async def replay_node(
    run_id: str,
    node_id: str,
    model: str | None = None,
    prompt: str | None = None,
) -> dict:  # type: ignore[type-arg]
    """Replay a single node from an existing run with optional overrides.

    Args:
        run_id: The original run to replay from.
        node_id: Which node to re-execute.
        model: Override the agent model (e.g. ``"gpt-4o"``).
        prompt: Override the node's system prompt.

    Returns ``{"new_run_id", "status", "node_output"}``.
    Imported (OTel) runs return ``{"error": ..., "code": "unsupported"}``.
    """
    exec_store, art_store = _get_stores()
    try:
        return await _t.replay_node(
            exec_store, art_store, run_id, node_id, model=model, prompt=prompt
        )
    finally:
        try:
            await exec_store.close()
        except Exception:  # noqa: BLE001
            pass


@mcp.tool()
async def eval_run(suite_path: str) -> dict:  # type: ignore[type-arg]
    """Run an eval suite and return the results.

    Args:
        suite_path: Path to the eval suite YAML file.

    Returns the full ``EvalResult`` dict (cases with verdicts, similarity, cost).
    """
    exec_store, art_store = _get_stores()
    try:
        return await _t.eval_run(exec_store, art_store, suite_path)
    finally:
        try:
            await exec_store.close()
        except Exception:  # noqa: BLE001
            pass


@mcp.tool()
async def get_artifact(artifact_id: str) -> dict:  # type: ignore[type-arg]
    """Return the full (untruncated) content of an artifact.

    This is the only tool that returns content without the 4 000-char limit.
    Use this when a ``debug_node`` response shows a ``[truncated ...]`` suffix.
    """
    exec_store, art_store = _get_stores()
    try:
        return await _t.get_artifact(exec_store, art_store, artifact_id)
    finally:
        try:
            await exec_store.close()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_server() -> None:
    """Start the MCP server (stdio transport).  Called by ``binex mcp serve``."""
    _log.info("Starting Binex MCP server (stdio)")
    mcp.run()
