"""CLI group: binex mcp serve."""

from __future__ import annotations

from typing import Any

import click

from binex.cli import get_stores


def _get_stores() -> Any:
    """Create default stores. Extracted for test patching."""
    return get_stores()


@click.group("mcp")
def mcp_group() -> None:
    """MCP server — expose Binex tools over the Model Context Protocol."""


@mcp_group.command("serve")
def mcp_serve() -> None:
    """Start the Binex MCP server (stdio transport).

    Connect your MCP client (Claude Desktop, Cursor, etc.) to this server
    to interact with Binex workflows via natural language.

    The server communicates over stdin/stdout using JSON-RPC.
    All diagnostic logging goes to stderr.

    \b
    Example claude_desktop_config.json entry:

        {
          "mcpServers": {
            "binex": {
              "command": "binex",
              "args": ["mcp", "serve"]
            }
          }
        }
    """
    from binex.mcp_server.server import run_server

    run_server()
