"""Generalized cost tracking beyond tokens (issue #79)."""

from __future__ import annotations

import asyncio
import os

import pytest

from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import CostRecord
from binex.models.task import TaskNode
from binex.runtime.cost_report import CostReporter


def _task() -> TaskNode:
    return TaskNode(id="t", run_id="r", node_id="n", agent="local://x")


def _art() -> Artifact:
    return Artifact(id="a", run_id="r", type="r", content={},
                    lineage=Lineage(produced_by="n"))


# ── CostReporter ─────────────────────────────────────────────────────────

def test_report_direct_cost():
    rep = CostReporter(_task())
    rep.report(cost=1.25)
    assert rep.record.cost == 1.25
    assert rep.record.provenance == "declared"
    assert rep.record.source == "agent_report"


def test_report_quantity_times_price():
    rep = CostReporter(_task())
    rep.report(unit="requests", quantity=10, unit_price=0.02)
    assert rep.record.cost == pytest.approx(0.2)
    assert rep.record.unit == "requests"


def test_report_convenience_units():
    rep = CostReporter(_task())
    rep.report(seconds=7200, unit_price=0.0001)
    assert rep.record.unit == "seconds"
    assert rep.record.quantity == 7200
    assert rep.record.cost == pytest.approx(0.72)


def test_report_characters():
    rep = CostReporter(_task())
    rep.report(characters=5000, unit_price=0.000016)
    assert rep.record.unit == "characters"
    assert rep.record.cost == pytest.approx(0.08)


# ── backward compatibility ───────────────────────────────────────────────

def test_cost_record_defaults_are_token_litellm():
    rec = CostRecord(id="c", run_id="r", task_id="n", source="llm_tokens")
    assert rec.unit == "tokens"
    assert rec.provenance == "litellm"


# ── LocalPythonAdapter integration ───────────────────────────────────────

@pytest.mark.asyncio
async def test_adapter_attaches_declared_cost():
    async def handler(task, inputs, report_cost):
        report_cost(seconds=60, unit_price=0.01)
        return [_art()]

    result = await LocalPythonAdapter(handler).execute(_task(), [], "trace")
    assert result.cost is not None
    assert result.cost.unit == "seconds"
    assert result.cost.cost == pytest.approx(0.6)


@pytest.mark.asyncio
async def test_adapter_no_cost_for_legacy_handler():
    async def handler(task, inputs):
        return [_art()]

    result = await LocalPythonAdapter(handler).execute(_task(), [], "trace")
    assert result.cost is None


# ── sqlite roundtrip + migration ─────────────────────────────────────────

def test_generalized_cost_sqlite_roundtrip(tmp_path):
    from binex.stores.backends.sqlite import SqliteExecutionStore

    async def _go():
        store = SqliteExecutionStore(os.path.join(tmp_path, "b.db"))
        await store.record_cost(CostRecord(
            id="c1", run_id="r", task_id="n", cost=0.72, source="agent_report",
            unit="seconds", quantity=7200, unit_price=0.0001, provenance="declared",
        ))
        costs = await store.list_costs("r")
        await store.close()
        return costs

    costs = asyncio.run(_go())
    assert costs[0].unit == "seconds"
    assert costs[0].quantity == 7200
    assert costs[0].provenance == "declared"


def test_cost_migration_on_legacy_db(tmp_path):
    import sqlite3

    from binex.stores.backends.sqlite import SqliteExecutionStore

    path = os.path.join(tmp_path, "old.db")
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE cost_records (id TEXT PRIMARY KEY, run_id TEXT NOT NULL, "
        "task_id TEXT NOT NULL, cost REAL NOT NULL DEFAULT 0.0, "
        "currency TEXT NOT NULL DEFAULT 'USD', source TEXT NOT NULL, "
        "prompt_tokens INTEGER, completion_tokens INTEGER, model TEXT, "
        "timestamp TEXT NOT NULL)"
    )
    con.execute(
        "INSERT INTO cost_records (id,run_id,task_id,cost,currency,source,timestamp) "
        "VALUES ('c0','r','n',0.5,'USD','llm_tokens','2026-01-01T00:00:00')"
    )
    con.commit()
    con.close()

    async def _go():
        store = SqliteExecutionStore(path)
        costs = await store.list_costs("r")   # triggers migration
        await store.close()
        return costs

    costs = asyncio.run(_go())
    assert costs[0].unit == "tokens"          # legacy default
    assert costs[0].provenance == "litellm"
