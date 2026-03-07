"""Tests for CLI cancel command (T059)."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from binex.cli.main import cli
from binex.models.execution import RunSummary
from binex.stores.backends.memory import InMemoryExecutionStore


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def exec_store_with_running_run():
    store = InMemoryExecutionStore()

    async def _populate():
        await store.create_run(RunSummary(
            run_id="run_active",
            workflow_name="test-pipeline",
            status="running",
            started_at=datetime(2026, 3, 7, 10, 0, 0, tzinfo=UTC),
            total_nodes=3,
            completed_nodes=1,
        ))
        await store.create_run(RunSummary(
            run_id="run_done",
            workflow_name="test-pipeline",
            status="completed",
            started_at=datetime(2026, 3, 7, 9, 0, 0, tzinfo=UTC),
            total_nodes=2,
            completed_nodes=2,
        ))

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(_populate())
    return store


class TestCancelCommand:
    def test_cancel_running_run(self, runner, exec_store_with_running_run):
        store = exec_store_with_running_run
        with patch("binex.cli.run._get_stores", return_value=(store, None)):
            result = runner.invoke(cli, ["cancel", "run_active"])
        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()

        # Verify status updated in store
        loop = asyncio.get_event_loop_policy().new_event_loop()
        run = loop.run_until_complete(store.get_run("run_active"))
        assert run.status == "cancelled"

    def test_cancel_nonexistent_run(self, runner, exec_store_with_running_run):
        store = exec_store_with_running_run
        with patch("binex.cli.run._get_stores", return_value=(store, None)):
            result = runner.invoke(cli, ["cancel", "run_nonexistent"])
        assert result.exit_code != 0

    def test_cancel_already_completed_run(self, runner, exec_store_with_running_run):
        store = exec_store_with_running_run
        with patch("binex.cli.run._get_stores", return_value=(store, None)):
            result = runner.invoke(cli, ["cancel", "run_done"])
        assert result.exit_code != 0
        assert "not running" in result.output.lower() or "cannot cancel" in result.output.lower()
