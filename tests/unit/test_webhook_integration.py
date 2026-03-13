"""Unit tests for webhook integration with orchestrator."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from binex.models.workflow import WebhookConfig, WorkflowSpec


# ---- US5: WebhookConfig parsing ----


class TestWebhookConfigParsing:
    def test_parses_from_workflow_yaml(self):
        """T031: WebhookConfig parses from workflow YAML."""
        spec_data = {
            "name": "test-wf",
            "webhook": {"url": "https://example.com/hook"},
            "nodes": {
                "a": {"agent": "llm://gpt-4o", "outputs": ["result"]},
            },
        }
        spec = WorkflowSpec(**spec_data)
        assert spec.webhook is not None
        assert spec.webhook.url == "https://example.com/hook"

    def test_webhook_none_when_absent(self):
        """T032: WebhookConfig is None when absent."""
        spec_data = {
            "name": "test-wf",
            "nodes": {
                "a": {"agent": "llm://gpt-4o", "outputs": ["result"]},
            },
        }
        spec = WorkflowSpec(**spec_data)
        assert spec.webhook is None

    def test_parses_from_yaml_string(self):
        """Parses webhook config from YAML string like real usage."""
        yaml_str = """
name: my-pipeline
webhook:
  url: "https://hooks.example.com/test"
nodes:
  analyze:
    agent: "llm://gpt-4o"
    outputs: [result]
"""
        data = yaml.safe_load(yaml_str)
        spec = WorkflowSpec(**data)
        assert spec.webhook is not None
        assert spec.webhook.url == "https://hooks.example.com/test"


# ---- US5: Orchestrator fires webhook on completion ----


class TestWebhookOnCompletion:
    @pytest.mark.asyncio
    async def test_fires_run_completed_webhook(self):
        """T033: orchestrator fires run.completed webhook on successful run."""
        from binex.runtime.orchestrator import Orchestrator
        from binex.stores.backends.memory import (
            InMemoryArtifactStore,
            InMemoryExecutionStore,
        )

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orchestrator = Orchestrator(art_store, exec_store)

        # Register a local adapter that returns successfully
        orchestrator.dispatcher.register_adapter("local://noop", AsyncMock(
            return_value=AsyncMock(
                artifacts=[],
                cost=None,
            ),
        ))

        spec = WorkflowSpec(
            name="test-wf",
            webhook=WebhookConfig(url="https://example.com/hook"),
            nodes={
                "a": {"agent": "local://noop", "outputs": ["result"]},
            },
        )

        with patch("binex.runtime.orchestrator.WebhookSender") as MockSender:
            mock_sender = AsyncMock()
            mock_sender.send = AsyncMock(return_value=True)
            MockSender.from_config.return_value = mock_sender

            summary = await orchestrator.run_workflow(spec)

            assert summary.status == "completed"
            mock_sender.send.assert_called_once()
            call_payload = mock_sender.send.call_args[0][0]
            assert call_payload["event"] == "run.completed"
            assert call_payload["run_id"] == summary.run_id
            assert call_payload["workflow_name"] == "test-wf"
            assert call_payload["data"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_no_webhook_when_not_configured(self):
        """T034: no webhook when not configured."""
        from binex.runtime.orchestrator import Orchestrator
        from binex.stores.backends.memory import (
            InMemoryArtifactStore,
            InMemoryExecutionStore,
        )

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orchestrator = Orchestrator(art_store, exec_store)

        orchestrator.dispatcher.register_adapter("local://noop", AsyncMock(
            return_value=AsyncMock(
                artifacts=[],
                cost=None,
            ),
        ))

        spec = WorkflowSpec(
            name="test-wf",
            nodes={
                "a": {"agent": "local://noop", "outputs": ["result"]},
            },
        )

        with patch("binex.runtime.orchestrator.WebhookSender") as MockSender:
            MockSender.from_config.return_value = None

            summary = await orchestrator.run_workflow(spec)
            assert summary.status == "completed"
            # from_config was called but returned None, so send should not be called
            MockSender.from_config.assert_called_once()


# ---- US6: Webhook on failure ----


class TestWebhookOnFailure:
    @pytest.mark.asyncio
    async def test_fires_run_failed_webhook(self):
        """T041: orchestrator fires run.failed webhook on failed run."""
        from binex.runtime.orchestrator import Orchestrator
        from binex.stores.backends.memory import (
            InMemoryArtifactStore,
            InMemoryExecutionStore,
        )

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orchestrator = Orchestrator(art_store, exec_store)

        # Register adapter whose execute method raises
        failing_adapter = AsyncMock()
        failing_adapter.execute = AsyncMock(side_effect=RuntimeError("node failed"))
        orchestrator.dispatcher.register_adapter("local://fail", failing_adapter)

        spec = WorkflowSpec(
            name="test-wf",
            webhook=WebhookConfig(url="https://example.com/hook"),
            nodes={
                "a": {"agent": "local://fail", "outputs": ["result"]},
            },
        )

        with patch("binex.runtime.orchestrator.WebhookSender") as MockSender:
            mock_sender = AsyncMock()
            mock_sender.send = AsyncMock(return_value=True)
            MockSender.from_config.return_value = mock_sender

            summary = await orchestrator.run_workflow(spec)

            assert summary.status == "failed"
            mock_sender.send.assert_called_once()
            call_payload = mock_sender.send.call_args[0][0]
            assert call_payload["event"] == "run.failed"
            assert call_payload["data"]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_webhook_retry_on_delivery_failure(self):
        """T042: webhook retry on delivery failure (3 attempts)."""
        from binex.webhook import WebhookSender

        sender = WebhookSender(url="https://example.com/hook")

        import httpx
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "500", request=MagicMock(), response=mock_response,
            ),
        )

        with patch("httpx.AsyncClient") as MockClient, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            client = AsyncMock()
            client.post = AsyncMock(return_value=mock_response)
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client

            result = await sender.send({"event": "run.failed"})
            assert result is False
            assert client.post.call_count == 3


# ---- US7: Webhook on budget exceeded ----


class TestWebhookOnBudgetExceeded:
    @pytest.mark.asyncio
    async def test_fires_budget_exceeded_webhook(self):
        """T046: orchestrator fires run.budget_exceeded webhook on over_budget."""
        from binex.models.cost import BudgetConfig
        from binex.runtime.orchestrator import Orchestrator
        from binex.stores.backends.memory import (
            InMemoryArtifactStore,
            InMemoryExecutionStore,
        )

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orchestrator = Orchestrator(art_store, exec_store)

        # Register adapter that "costs" something
        from binex.models.cost import CostRecord, ExecutionResult

        async def _execute(task, artifacts, trace_id, **kwargs):
            cost = CostRecord(
                id=f"c_{task.node_id}",
                run_id=task.run_id,
                task_id=task.node_id,
                cost=2.0,
                source="llm_tokens",
                timestamp=datetime.now(UTC),
            )
            return ExecutionResult(artifacts=[], cost=cost)

        expensive_adapter = AsyncMock()
        expensive_adapter.execute = _execute
        orchestrator.dispatcher.register_adapter("local://expensive", expensive_adapter)

        spec = WorkflowSpec(
            name="test-wf",
            webhook=WebhookConfig(url="https://example.com/hook"),
            budget=BudgetConfig(max_cost=0.01, policy="stop"),
            nodes={
                "a": {"agent": "local://expensive", "outputs": ["r1"]},
                "b": {"agent": "local://expensive", "outputs": ["r2"],
                       "depends_on": ["a"]},
            },
        )

        with patch("binex.runtime.orchestrator.WebhookSender") as MockSender:
            mock_sender = AsyncMock()
            mock_sender.send = AsyncMock(return_value=True)
            MockSender.from_config.return_value = mock_sender

            summary = await orchestrator.run_workflow(spec)

            assert summary.status == "over_budget"
            mock_sender.send.assert_called_once()
            call_payload = mock_sender.send.call_args[0][0]
            assert call_payload["event"] == "run.budget_exceeded"
            assert call_payload["data"]["status"] == "over_budget"
            assert "max_cost" in call_payload["data"]
