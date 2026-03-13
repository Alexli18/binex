"""Tests for A2A Gateway CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from binex.cli.main import cli

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gateway_yaml(tmp_path, *, agents=None, auth=None):
    """Write a minimal gateway.yaml and return its path."""
    import yaml

    data = {
        "host": "127.0.0.1",
        "port": 9999,
        "agents": agents or [
            {
                "name": "summarizer",
                "endpoint": "http://localhost:5001",
                "capabilities": ["summarize"],
            },
        ],
        "health": {"interval_s": 60, "timeout_ms": 3000},
    }
    if auth is not None:
        data["auth"] = auth
    p = tmp_path / "gateway.yaml"
    p.write_text(yaml.dump(data))
    return str(p)


def _mock_uvicorn():
    """Return a mock uvicorn module."""
    mock = MagicMock()
    return mock


def _mock_httpx_ok(json_data):
    """Return a mock httpx module whose .get() returns a successful response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = json_data
    mock_response.raise_for_status = MagicMock()
    mock = MagicMock()
    mock.get.return_value = mock_response
    return mock


def _mock_httpx_error():
    """Return a mock httpx module whose .get() raises an exception."""
    mock = MagicMock()
    mock.get.side_effect = Exception("Connection refused")
    return mock


# ---------------------------------------------------------------------------
# T015.1 — `binex gateway` (start server)
# ---------------------------------------------------------------------------

class TestGatewayStart:
    """Tests for the default `binex gateway` command (server start)."""

    def test_start_with_config(self, tmp_path):
        config_path = _gateway_yaml(tmp_path)
        mock_uv = _mock_uvicorn()
        runner = CliRunner()
        with patch("binex.cli.gateway_cmd._import_uvicorn", return_value=mock_uv), \
             patch("binex.cli.gateway_cmd.create_app", return_value=MagicMock()):
            result = runner.invoke(cli, ["gateway", "--config", config_path])

        assert result.exit_code == 0, result.output
        assert "A2A Gateway starting" in result.output
        assert "127.0.0.1:9999" in result.output
        assert "Agents: 1 registered" in result.output
        mock_uv.run.assert_called_once()

    def test_start_no_config_error(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["gateway", "--config", str(tmp_path / "missing.yaml")])

        assert result.exit_code == 1
        assert "Error" in (result.output + (result.output or ""))

    def test_start_shows_auth_info(self, tmp_path):
        config_path = _gateway_yaml(
            tmp_path,
            auth={"type": "api_key", "keys": [{"name": "test", "key": "sk-abc123"}]},
        )
        mock_uv = _mock_uvicorn()
        runner = CliRunner()
        with patch("binex.cli.gateway_cmd._import_uvicorn", return_value=mock_uv), \
             patch("binex.cli.gateway_cmd.create_app", return_value=MagicMock()):
            result = runner.invoke(cli, ["gateway", "--config", config_path])

        assert result.exit_code == 0, result.output
        assert "Auth: api_key (1 keys configured)" in result.output

    def test_start_shows_disabled_auth(self, tmp_path):
        config_path = _gateway_yaml(tmp_path)
        mock_uv = _mock_uvicorn()
        runner = CliRunner()
        with patch("binex.cli.gateway_cmd._import_uvicorn", return_value=mock_uv), \
             patch("binex.cli.gateway_cmd.create_app", return_value=MagicMock()):
            result = runner.invoke(cli, ["gateway", "--config", config_path])

        assert result.exit_code == 0, result.output
        assert "disabled" in result.output

    def test_start_custom_host_port(self, tmp_path):
        config_path = _gateway_yaml(tmp_path)
        mock_uv = _mock_uvicorn()
        runner = CliRunner()
        with patch("binex.cli.gateway_cmd._import_uvicorn", return_value=mock_uv), \
             patch("binex.cli.gateway_cmd.create_app", return_value=MagicMock()):
            result = runner.invoke(
                cli, ["gateway", "--config", config_path, "--host", "0.0.0.0", "--port", "7777"],
            )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_uv.run.call_args
        assert call_kwargs[1]["host"] == "0.0.0.0"
        assert call_kwargs[1]["port"] == 7777

    def test_start_health_check_interval(self, tmp_path):
        config_path = _gateway_yaml(tmp_path)
        mock_uv = _mock_uvicorn()
        runner = CliRunner()
        with patch("binex.cli.gateway_cmd._import_uvicorn", return_value=mock_uv), \
             patch("binex.cli.gateway_cmd.create_app", return_value=MagicMock()):
            result = runner.invoke(cli, ["gateway", "--config", config_path])

        assert result.exit_code == 0, result.output
        assert "Health check: every 60s" in result.output


# ---------------------------------------------------------------------------
# T015.2 — `binex gateway status`
# ---------------------------------------------------------------------------

class TestGatewayStatus:
    """Tests for `binex gateway status`."""

    def test_status_success(self):
        mock_hx = _mock_httpx_ok({
            "status": "healthy",
            "agents_total": 3,
            "agents_alive": 2,
            "agents_degraded": 1,
            "agents_down": 0,
        })
        runner = CliRunner()
        with patch("binex.cli.gateway_cmd._import_httpx", return_value=mock_hx):
            result = runner.invoke(cli, ["gateway", "status"])

        assert result.exit_code == 0, result.output
        assert "http://localhost:8420" in result.output
        assert "healthy" in result.output
        assert "3 total" in result.output

    def test_status_json_output(self):
        mock_hx = _mock_httpx_ok({
            "status": "healthy",
            "agents_total": 2,
            "agents_alive": 2,
            "agents_degraded": 0,
            "agents_down": 0,
        })
        runner = CliRunner()
        with patch("binex.cli.gateway_cmd._import_httpx", return_value=mock_hx):
            result = runner.invoke(cli, ["gateway", "status", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["gateway"] == "http://localhost:8420"
        assert data["status"] == "healthy"
        assert data["agents_total"] == 2

    def test_status_custom_gateway_url(self):
        mock_hx = _mock_httpx_ok({
            "status": "healthy",
            "agents_total": 1,
            "agents_alive": 1,
            "agents_degraded": 0,
            "agents_down": 0,
        })
        runner = CliRunner()
        with patch("binex.cli.gateway_cmd._import_httpx", return_value=mock_hx):
            result = runner.invoke(cli, ["gateway", "status", "--gateway", "http://my-gw:9000"])

        assert result.exit_code == 0, result.output
        mock_hx.get.assert_called_once_with("http://my-gw:9000/health", timeout=10.0)

    def test_status_connection_error(self):
        mock_hx = _mock_httpx_error()
        runner = CliRunner()
        with patch("binex.cli.gateway_cmd._import_httpx", return_value=mock_hx):
            result = runner.invoke(cli, ["gateway", "status"])

        assert result.exit_code == 1
        assert "Cannot connect" in result.output
        assert "http://localhost:8420" in result.output


# ---------------------------------------------------------------------------
# T015.3 — `binex gateway agents`
# ---------------------------------------------------------------------------

class TestGatewayAgents:
    """Tests for `binex gateway agents`."""

    def test_agents_success(self):
        mock_hx = _mock_httpx_ok({
            "agents": [
                {
                    "name": "summarizer",
                    "endpoint": "http://localhost:5001",
                    "capabilities": ["summarize"],
                    "priority": 0,
                    "status": "alive",
                    "last_latency_ms": 45,
                },
                {
                    "name": "translator",
                    "endpoint": "http://localhost:5002",
                    "capabilities": ["translate"],
                    "priority": 1,
                    "status": "down",
                    "last_latency_ms": None,
                },
            ],
        })
        runner = CliRunner()
        with patch("binex.cli.gateway_cmd._import_httpx", return_value=mock_hx):
            result = runner.invoke(cli, ["gateway", "agents"])

        assert result.exit_code == 0, result.output
        assert "summarizer" in result.output
        assert "translator" in result.output
        assert "alive" in result.output

    def test_agents_json_output(self):
        agents_data = {
            "agents": [
                {
                    "name": "summarizer",
                    "endpoint": "http://localhost:5001",
                    "capabilities": ["summarize"],
                    "priority": 0,
                    "status": "alive",
                    "last_latency_ms": 45,
                },
            ],
        }
        mock_hx = _mock_httpx_ok(agents_data)
        runner = CliRunner()
        with patch("binex.cli.gateway_cmd._import_httpx", return_value=mock_hx):
            result = runner.invoke(cli, ["gateway", "agents", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data == agents_data

    def test_agents_connection_error(self):
        mock_hx = _mock_httpx_error()
        runner = CliRunner()
        with patch("binex.cli.gateway_cmd._import_httpx", return_value=mock_hx):
            result = runner.invoke(cli, ["gateway", "agents"])

        assert result.exit_code == 1
        assert "Cannot connect" in result.output

    def test_agents_empty_list(self):
        mock_hx = _mock_httpx_ok({"agents": []})
        runner = CliRunner()
        with patch("binex.cli.gateway_cmd._import_httpx", return_value=mock_hx):
            result = runner.invoke(cli, ["gateway", "agents"])

        assert result.exit_code == 0, result.output
        assert "No agents" in result.output


# ---------------------------------------------------------------------------
# T017 — `--gateway` flag on `binex run`
# ---------------------------------------------------------------------------

class TestRunGatewayFlag:
    """Tests for --gateway option on binex run."""

    def test_run_accepts_gateway_flag(self, tmp_path):
        """Verify --gateway is accepted without error (won't actually run)."""
        wf = tmp_path / "workflow.yaml"
        wf.write_text(
            "name: test\nnodes:\n  a:\n    agent: local://echo\n    prompt: hi\n"
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["run", str(wf), "--gateway", "http://gw:8420"])
        # It will fail at execution (no stores), but should NOT fail with
        # "no such option: --gateway"
        assert "no such option" not in (result.output or "")


# ---------------------------------------------------------------------------
# T018 — register_workflow_adapters with gateway_url
# ---------------------------------------------------------------------------

class TestAdapterRegistryGatewayUrl:
    """Tests for register_workflow_adapters with gateway_url parameter."""

    def test_gateway_url_creates_http_adapter(self):
        """When gateway_url is set, a2a:// agents use the external gateway."""
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.models.workflow import NodeSpec, WorkflowSpec
        from binex.runtime.dispatcher import Dispatcher

        spec = WorkflowSpec(
            name="test",
            nodes={
                "agent_a": NodeSpec(
                    agent="a2a://summarize",
                    prompt="Do something",
                    outputs=["result"],
                ),
            },
        )
        dispatcher = Dispatcher()
        register_workflow_adapters(
            dispatcher, spec, gateway_url="http://external-gw:8420",
        )

        adapter = dispatcher._adapters.get("a2a://summarize")
        assert adapter is not None
        # The adapter should point to the external gateway URL
        assert hasattr(adapter, "_gateway_url")
        assert adapter._gateway_url == "http://external-gw:8420"

    def test_gateway_url_none_uses_embedded(self):
        """When gateway_url is None, embedded gateway is used (original behavior)."""
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.models.workflow import NodeSpec, WorkflowSpec
        from binex.runtime.dispatcher import Dispatcher

        spec = WorkflowSpec(
            name="test",
            nodes={
                "agent_a": NodeSpec(
                    agent="a2a://http://localhost:5001",
                    prompt="Do something",
                    outputs=["result"],
                ),
            },
        )
        dispatcher = Dispatcher()

        with patch("binex.gateway.create_gateway") as mock_cg:
            mock_gw = MagicMock()
            mock_gw._config = None
            mock_cg.return_value = mock_gw
            register_workflow_adapters(dispatcher, spec)

        adapter = dispatcher._adapters.get("a2a://http://localhost:5001")
        assert adapter is not None
        # Should NOT have _gateway_url attribute (uses embedded gateway)
        assert not hasattr(adapter, "_gateway_url")
