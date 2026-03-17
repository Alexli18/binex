"""MCP client manager — connects to MCP servers, exposes tools as ToolDefinitions."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from binex.models.workflow import McpServerConfig
from binex.tools._core import ToolDefinition

# Lazy imports — resolved at connect() time, but patchable at module level
ClientSession: Any = None
stdio_client: Any = None
sse_client: Any = None
StdioServerParameters: Any = None

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = 30  # seconds — max wait for session.initialize()


class McpClientManager:
    """Manages connections to MCP servers declared in workflow YAML."""

    def __init__(self, servers: dict[str, McpServerConfig]) -> None:
        self._configs = dict(servers)
        self._clients: dict[str, Any] = {}
        self._tools_cache: dict[str, list[ToolDefinition]] = {}

    @property
    def server_names(self) -> list[str]:
        """Return sorted list of configured server names."""
        return sorted(self._configs)

    @staticmethod
    def _ensure_mcp_imports() -> None:
        """Import MCP SDK lazily (only when actually connecting)."""
        global ClientSession, stdio_client, sse_client, StdioServerParameters  # noqa: N814
        if ClientSession is not None:
            return
        import mcp
        import mcp.client.sse
        import mcp.client.stdio

        ClientSession = mcp.ClientSession
        stdio_client = mcp.client.stdio.stdio_client
        StdioServerParameters = mcp.client.stdio.StdioServerParameters
        sse_client = mcp.client.sse.sse_client

    @staticmethod
    def _detect_transport(cfg: McpServerConfig) -> str:
        """Detect transport type from config."""
        return "stdio" if cfg.command else "sse"

    async def connect(self, name: str) -> None:
        """Connect to an MCP server by name."""
        if name not in self._configs:
            raise ValueError(f"Unknown MCP server: '{name}'")
        if name in self._clients:
            return  # already connected

        cfg = self._configs[name]
        transport = self._detect_transport(cfg)
        logger.info("Connecting to MCP server '%s' via %s", name, transport)

        self._ensure_mcp_imports()

        if transport == "stdio":
            params = StdioServerParameters(
                command=cfg.command,
                args=cfg.args,
                env=cfg.env or None,
            )
            client_ctx = stdio_client(params)
        else:
            client_ctx = sse_client(cfg.url)

        # CRIT-1 fix: ensure client_ctx is closed if session setup fails
        try:
            transport_ctx = await client_ctx.__aenter__()
            read_stream, write_stream = transport_ctx
            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()
            await asyncio.wait_for(
                session.initialize(), timeout=CONNECT_TIMEOUT,
            )
        except Exception:
            try:
                await client_ctx.__aexit__(None, None, None)
            except Exception as cleanup_exc:
                logger.warning(
                    "Error cleaning up transport for '%s': %s",
                    name, cleanup_exc,
                )
            raise

        self._clients[name] = {
            "session": session,
            "client_ctx": client_ctx,
        }
        logger.info("Connected to MCP server '%s'", name)

    async def get_tools(self, name: str) -> list[ToolDefinition]:
        """Get all tools from an MCP server as ToolDefinitions.

        Tool names are namespaced as ``{server_name}__{tool_name}``
        to prevent collisions with built-in tools or tools from other
        MCP servers.
        """
        if name not in self._configs:
            raise ValueError(f"Unknown MCP server: '{name}'")

        if name in self._tools_cache:
            return self._tools_cache[name]

        if name not in self._clients:
            await self.connect(name)

        session = self._clients[name]["session"]
        result = await session.list_tools()

        tools: list[ToolDefinition] = []
        for mcp_tool in result.tools:
            # CRIT-2 fix: namespace tool names to avoid collisions
            namespaced_name = f"{name}__{mcp_tool.name}"
            tool_def = ToolDefinition(
                name=namespaced_name,
                description=mcp_tool.description or mcp_tool.name,
                parameters=mcp_tool.inputSchema or {
                    "type": "object", "properties": {},
                },
                callable=self._make_tool_caller(name, mcp_tool.name),
                is_async=True,
            )
            tools.append(tool_def)

        self._tools_cache[name] = tools
        return tools

    def _make_tool_caller(
        self, server_name: str, tool_name: str,
    ) -> Any:
        """Create an async callable that invokes an MCP tool.

        Uses the original (non-namespaced) tool_name for the actual
        MCP call_tool invocation.
        """

        async def call_tool(**kwargs: Any) -> str:
            session = self._clients[server_name]["session"]
            result = await session.call_tool(tool_name, arguments=kwargs)
            parts = []
            for content in result.content:
                if hasattr(content, "text"):
                    parts.append(content.text)
                else:
                    parts.append(str(content))
            return "\n".join(parts)

        return call_tool

    async def close_all(self) -> None:
        """Close all MCP server connections."""
        for name, client_info in list(self._clients.items()):
            try:
                session = client_info["session"]
                client_ctx = client_info["client_ctx"]
                await session.__aexit__(None, None, None)
                await client_ctx.__aexit__(None, None, None)
                logger.info("Closed MCP server '%s'", name)
            except Exception as exc:
                logger.warning("Error closing MCP server '%s': %s", name, exc)
        self._clients.clear()
        self._tools_cache.clear()
