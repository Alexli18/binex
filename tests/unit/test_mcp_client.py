"""Tests for MCP client manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.models.workflow import McpServerConfig
from binex.tools.mcp_client import McpClientManager


class TestMcpClientManager:
    def test_init_empty(self):
        mgr = McpClientManager({})
        assert mgr.server_names == []

    def test_init_with_servers(self):
        mgr = McpClientManager({
            "files": McpServerConfig(command="npx", args=["@mcp/fs"]),
            "api": McpServerConfig(url="http://localhost:3001"),
        })
        assert mgr.server_names == ["api", "files"]

    @pytest.mark.asyncio
    async def test_get_tools_unknown_server(self):
        mgr = McpClientManager({})
        with pytest.raises(ValueError, match="Unknown MCP server"):
            await mgr.get_tools("nonexistent")

    @pytest.mark.asyncio
    async def test_connect_unknown_server(self):
        mgr = McpClientManager({})
        with pytest.raises(ValueError, match="Unknown MCP server"):
            await mgr.connect("nonexistent")

    def test_detect_transport_stdio(self):
        cfg = McpServerConfig(command="npx", args=["@mcp/test"])
        assert McpClientManager._detect_transport(cfg) == "stdio"

    def test_detect_transport_http(self):
        cfg = McpServerConfig(url="http://localhost:3001")
        assert McpClientManager._detect_transport(cfg) == "sse"

    @pytest.mark.asyncio
    async def test_close_all_empty(self):
        mgr = McpClientManager({})
        await mgr.close_all()  # should not raise


class TestMcpConnectResourceCleanup:
    """CRIT-1: Verify transport is cleaned up if session setup fails."""

    @pytest.mark.asyncio
    async def test_transport_closed_on_session_failure(self):
        """If ClientSession.__aenter__ raises, client_ctx must be closed."""
        mgr = McpClientManager({
            "test": McpServerConfig(command="echo", args=["hello"]),
        })

        mock_client_ctx = AsyncMock()
        mock_transport = (MagicMock(), MagicMock())
        mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_transport)
        mock_client_ctx.__aexit__ = AsyncMock()

        mock_session_cls = MagicMock()
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(
            side_effect=ConnectionError("session failed"),
        )
        mock_session_cls.return_value = mock_session

        with (
            patch(
                "binex.tools.mcp_client.stdio_client",
                return_value=mock_client_ctx,
            ),
            patch(
                "binex.tools.mcp_client.StdioServerParameters",
                MagicMock(),
            ),
            patch("binex.tools.mcp_client.ClientSession", mock_session_cls),
        ):
            with pytest.raises(ConnectionError, match="session failed"):
                await mgr.connect("test")

        # client_ctx.__aexit__ must have been called for cleanup
        mock_client_ctx.__aexit__.assert_awaited_once()
        # Server should NOT be in _clients
        assert "test" not in mgr._clients

    @pytest.mark.asyncio
    async def test_transport_closed_on_initialize_failure(self):
        """If session.initialize() raises, client_ctx must be closed."""
        mgr = McpClientManager({
            "test": McpServerConfig(command="echo", args=["hello"]),
        })

        mock_client_ctx = AsyncMock()
        mock_transport = (MagicMock(), MagicMock())
        mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_transport)
        mock_client_ctx.__aexit__ = AsyncMock()

        mock_session_cls = MagicMock()
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.initialize = AsyncMock(
            side_effect=RuntimeError("init failed"),
        )
        mock_session_cls.return_value = mock_session

        with (
            patch(
                "binex.tools.mcp_client.stdio_client",
                return_value=mock_client_ctx,
            ),
            patch(
                "binex.tools.mcp_client.StdioServerParameters",
                MagicMock(),
            ),
            patch("binex.tools.mcp_client.ClientSession", mock_session_cls),
        ):
            with pytest.raises(RuntimeError, match="init failed"):
                await mgr.connect("test")

        mock_client_ctx.__aexit__.assert_awaited_once()
        assert "test" not in mgr._clients


class TestMcpConnectTimeout:
    """WARN-2: session.initialize() must have a timeout."""

    @pytest.mark.asyncio
    async def test_initialize_timeout(self):
        """If session.initialize() hangs, should raise TimeoutError."""
        import asyncio

        mgr = McpClientManager({
            "test": McpServerConfig(command="echo", args=["hello"]),
        })

        mock_client_ctx = AsyncMock()
        mock_transport = (MagicMock(), MagicMock())
        mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_transport)
        mock_client_ctx.__aexit__ = AsyncMock()

        mock_session_cls = MagicMock()
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)

        # Simulate hanging initialize
        async def slow_init():
            await asyncio.sleep(999)

        mock_session.initialize = slow_init
        mock_session_cls.return_value = mock_session

        with (
            patch(
                "binex.tools.mcp_client.stdio_client",
                return_value=mock_client_ctx,
            ),
            patch(
                "binex.tools.mcp_client.StdioServerParameters",
                MagicMock(),
            ),
            patch("binex.tools.mcp_client.ClientSession", mock_session_cls),
            patch("binex.tools.mcp_client.CONNECT_TIMEOUT", 0.1),
        ):
            with pytest.raises(asyncio.TimeoutError):
                await mgr.connect("test")

        # Transport must be cleaned up
        mock_client_ctx.__aexit__.assert_awaited_once()


class TestMcpToolNamespacing:
    """CRIT-2: MCP tools must be namespaced to prevent name collisions."""

    @pytest.mark.asyncio
    async def test_tools_are_namespaced(self):
        """MCP tool names should be prefixed with server_name__."""
        mgr = McpClientManager({
            "files": McpServerConfig(command="npx", args=["@mcp/fs"]),
        })

        # Mock connection and tool listing
        mock_tool = MagicMock()
        mock_tool.name = "read_file"
        mock_tool.description = "Read a file"
        mock_tool.inputSchema = {"type": "object", "properties": {}}

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.tools = [mock_tool]
        mock_session.list_tools = AsyncMock(return_value=mock_result)

        mgr._clients["files"] = {"session": mock_session, "client_ctx": None}

        tools = await mgr.get_tools("files")
        assert len(tools) == 1
        assert tools[0].name == "files__read_file"
        assert tools[0].description == "Read a file"
        assert tools[0].is_async is True

    @pytest.mark.asyncio
    async def test_namespaced_tools_no_collision_with_builtins(self):
        """MCP tool 'calculator' should not collide with builtin://calculator."""
        from binex.tools.builtins import get_builtin

        mgr = McpClientManager({
            "mathserver": McpServerConfig(command="node", args=["math.js"]),
        })

        mock_tool = MagicMock()
        mock_tool.name = "calculator"
        mock_tool.description = "Server calculator"
        mock_tool.inputSchema = {"type": "object", "properties": {}}

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.tools = [mock_tool]
        mock_session.list_tools = AsyncMock(return_value=mock_result)

        mgr._clients["mathserver"] = {
            "session": mock_session, "client_ctx": None,
        }

        mcp_tools = await mgr.get_tools("mathserver")
        builtin_calc = get_builtin("calculator")

        # Names must differ
        assert mcp_tools[0].name == "mathserver__calculator"
        assert builtin_calc.name == "calculator"
        assert mcp_tools[0].name != builtin_calc.name

    @pytest.mark.asyncio
    async def test_tool_caller_uses_original_name(self):
        """_make_tool_caller should call MCP with original tool name."""
        mgr = McpClientManager({
            "srv": McpServerConfig(command="echo", args=[]),
        })

        mock_session = MagicMock()
        mock_call_result = MagicMock()
        mock_content = MagicMock()
        mock_content.text = "result"
        mock_call_result.content = [mock_content]
        mock_session.call_tool = AsyncMock(return_value=mock_call_result)

        mgr._clients["srv"] = {"session": mock_session, "client_ctx": None}

        caller = mgr._make_tool_caller("srv", "original_name")
        result = await caller(arg1="value")

        # Must call MCP with the original (non-namespaced) name
        mock_session.call_tool.assert_awaited_once_with(
            "original_name", arguments={"arg1": "value"},
        )
        assert result == "result"
