"""Shared progress wrappers for CLI commands that run workflows.

Both ``binex run`` and ``binex hello`` monkey-patch the orchestrator's
``_execute_node`` to display progress.  This module extracts the common
patching logic so each caller only supplies a small callback for its own
artifact-collection needs.
"""

from __future__ import annotations

import sys
import time as _time
from collections.abc import Callable
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from binex.runtime.orchestrator import Orchestrator


def can_use_live() -> bool:
    """Return True when rich live display is available and output is a TTY."""
    from binex.cli import has_rich

    return has_rich() and sys.stderr.isatty()


# ---------------------------------------------------------------------------
# Verbose (plain-text) wrapper
# ---------------------------------------------------------------------------

def install_verbose_wrapper(
    orch: Orchestrator,
    *,
    on_node_done: Callable[[str, dict], None] | None = None,
) -> None:
    """Monkey-patch *orch* to print per-node progress lines.

    Parameters
    ----------
    orch:
        The orchestrator whose ``_execute_node`` will be wrapped.
    on_node_done:
        Optional callback ``(node_id, node_artifacts_dict) -> None`` invoked
        after each node completes.  Callers use this to collect artifacts in
        their own format.
    """
    original_execute = orch._execute_node
    counter = [0]

    async def _verbose_execute(
        spec_, dag_, scheduler_, run_id_, trace_id_, node_id_, node_artifacts_,
        accumulated_cost_=0.0, node_artifacts_history_=None,
    ):
        counter[0] += 1
        total = len(spec_.nodes)
        click.echo(f"\n  [{counter[0]}/{total}] {node_id_} ...", err=True)

        node_spec = spec_.nodes.get(node_id_)
        if node_spec and node_spec.depends_on:
            for dep in node_spec.depends_on:
                click.echo(f"        <- {dep}", err=True)

        await original_execute(
            spec_, dag_, scheduler_, run_id_, trace_id_,
            node_id_, node_artifacts_, accumulated_cost_, node_artifacts_history_,
        )

        if on_node_done is not None:
            on_node_done(node_id_, node_artifacts_)

    orch._execute_node = _verbose_execute


# ---------------------------------------------------------------------------
# Live (rich table) wrapper
# ---------------------------------------------------------------------------

def install_live_wrapper(
    orch: Orchestrator,
    live_table,
    live,
    *,
    on_node_done: Callable[[str, dict], None] | None = None,
) -> None:
    """Monkey-patch *orch* to update a ``LiveRunTable`` on each node.

    Parameters
    ----------
    orch:
        The orchestrator whose ``_execute_node`` will be wrapped.
    live_table:
        A ``LiveRunTable`` instance to update with node status.
    live:
        The ``rich.live.Live`` context that renders *live_table*.
    on_node_done:
        Optional callback ``(node_id, node_artifacts_dict) -> None`` invoked
        in the ``finally`` block after each node, regardless of success.
    """
    original_execute = orch._execute_node

    async def _live_execute(
        spec_, dag_, scheduler_, run_id_, trace_id_, node_id_, node_artifacts_,
        accumulated_cost_=0.0, node_artifacts_history_=None,
    ):
        live_table.update_node(node_id_, "running")
        live.update(live_table.build())
        t0 = _time.monotonic()
        try:
            await original_execute(
                spec_, dag_, scheduler_, run_id_, trace_id_,
                node_id_, node_artifacts_, accumulated_cost_, node_artifacts_history_,
            )
            elapsed = _time.monotonic() - t0
            live_table.update_node(
                node_id_, "completed", latency=f"{elapsed:.2f}s",
            )
        except Exception as exc:
            elapsed = _time.monotonic() - t0
            live_table.update_node(
                node_id_, "failed",
                latency=f"{elapsed:.2f}s",
                error=str(exc)[:50],
            )
            raise
        finally:
            if on_node_done is not None:
                on_node_done(node_id_, node_artifacts_)
            live.update(live_table.build())

    orch._execute_node = _live_execute
