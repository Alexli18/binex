"""Tests for McpServerConfig model and WorkflowSpec.mcp_servers field."""

import pytest

from binex.models.workflow import McpServerConfig, WorkflowSpec


class TestMcpServerConfig:
    def test_stdio_config(self):
        cfg = McpServerConfig(command="npx", args=["@anthropic/mcp-filesystem", "/tmp"])
        assert cfg.command == "npx"
        assert cfg.args == ["@anthropic/mcp-filesystem", "/tmp"]
        assert cfg.url is None
        assert cfg.env == {}

    def test_http_config(self):
        cfg = McpServerConfig(url="http://localhost:3001/sse")
        assert cfg.url == "http://localhost:3001/sse"
        assert cfg.command is None

    def test_stdio_with_env(self):
        cfg = McpServerConfig(command="node", args=["server.js"], env={"NODE_ENV": "prod"})
        assert cfg.env == {"NODE_ENV": "prod"}

    def test_must_have_command_or_url(self):
        with pytest.raises(ValueError, match="command.*url"):
            McpServerConfig()

    def test_both_command_and_url_raises(self):
        with pytest.raises(ValueError, match="not both"):
            McpServerConfig(command="npx", url="http://localhost:3001")


class TestWorkflowSpecMcp:
    def test_mcp_servers_default_empty(self):
        spec = WorkflowSpec(
            name="test",
            nodes={"a": {"agent": "llm://openai/gpt-4", "outputs": ["out"]}},
        )
        assert spec.mcp_servers == {}

    def test_mcp_servers_parsed(self):
        spec = WorkflowSpec(
            name="test",
            nodes={"a": {"agent": "llm://openai/gpt-4", "outputs": ["out"]}},
            mcp_servers={
                "files": {"command": "npx", "args": ["@anthropic/mcp-filesystem"]},
                "api": {"url": "http://localhost:3001"},
            },
        )
        assert "files" in spec.mcp_servers
        assert spec.mcp_servers["files"].command == "npx"
        assert spec.mcp_servers["api"].url == "http://localhost:3001"

    def test_mcp_servers_empty_dict(self):
        spec = WorkflowSpec(
            name="test",
            nodes={"a": {"agent": "llm://openai/gpt-4", "outputs": ["out"]}},
            mcp_servers={},
        )
        assert spec.mcp_servers == {}


class TestToolUriValidation:
    """Tests for builtin:// and mcp:// tool URI validation."""

    def test_valid_builtin_tool(self):
        from binex.workflow_spec.validator import validate_workflow

        spec = WorkflowSpec(
            name="test",
            nodes={"a": {
                "agent": "llm://openai/gpt-4",
                "outputs": ["out"],
                "tools": ["builtin://calculator"],
            }},
        )
        errors = validate_workflow(spec)
        assert not any("built-in" in e for e in errors)

    def test_invalid_builtin_tool(self):
        from binex.workflow_spec.validator import validate_workflow

        spec = WorkflowSpec(
            name="test",
            nodes={"a": {
                "agent": "llm://openai/gpt-4",
                "outputs": ["out"],
                "tools": ["builtin://nonexistent_tool"],
            }},
        )
        errors = validate_workflow(spec)
        assert any("nonexistent_tool" in e for e in errors)

    def test_valid_mcp_tool(self):
        from binex.workflow_spec.validator import validate_workflow

        spec = WorkflowSpec(
            name="test",
            nodes={"a": {
                "agent": "llm://openai/gpt-4",
                "outputs": ["out"],
                "tools": ["mcp://files"],
            }},
            mcp_servers={
                "files": {"command": "npx", "args": ["@mcp/fs"]},
            },
        )
        errors = validate_workflow(spec)
        assert not any("mcp://" in e for e in errors)

    def test_mcp_tool_unknown_server(self):
        from binex.workflow_spec.validator import validate_workflow

        spec = WorkflowSpec(
            name="test",
            nodes={"a": {
                "agent": "llm://openai/gpt-4",
                "outputs": ["out"],
                "tools": ["mcp://missing_server"],
            }},
        )
        errors = validate_workflow(spec)
        assert any("missing_server" in e for e in errors)

    def test_mixed_valid_tools(self):
        from binex.workflow_spec.validator import validate_workflow

        spec = WorkflowSpec(
            name="test",
            nodes={"a": {
                "agent": "llm://openai/gpt-4",
                "outputs": ["out"],
                "tools": [
                    "builtin://calculator",
                    "builtin://dice_roll",
                    "mcp://api",
                ],
            }},
            mcp_servers={
                "api": {"url": "http://localhost:3001"},
            },
        )
        errors = validate_workflow(spec)
        assert not errors
