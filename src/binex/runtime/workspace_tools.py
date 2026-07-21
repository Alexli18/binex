"""Workspace-jailed file tools for LLM nodes (#75).

Builds ``read_file`` / ``write_file`` / ``list_files`` ToolDefinitions bound to a
specific :class:`~binex.runtime.workspace.Workspace`. Every path goes through
``Workspace.resolve`` — jailed to the workspace root — so a model (or a
prompt-injected one) cannot read or write outside the run's sandbox.
"""

from __future__ import annotations

from binex.runtime.workspace import Workspace, WorkspaceError
from binex.tools._core import ToolDefinition


def make_workspace_tools(workspace: Workspace) -> list[ToolDefinition]:
    """Return file tools bound (jailed) to ``workspace``."""

    def read_file(path: str) -> str:
        try:
            return workspace.read_file(path)
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        except WorkspaceError as exc:
            return f"Error: {exc}"
        except Exception as exc:  # noqa: BLE001 — surface as a tool error, not a crash
            return f"Error reading {path}: {exc}"

    def write_file(path: str, content: str) -> str:
        try:
            n = workspace.write_file(path, content)
            return f"Written {n} bytes to {path}"
        except WorkspaceError as exc:
            return f"Error: {exc}"
        except Exception as exc:  # noqa: BLE001
            return f"Error writing {path}: {exc}"

    def list_files(subdir: str = ".") -> str:
        try:
            files = workspace.list_files(subdir)
        except WorkspaceError as exc:
            return f"Error: {exc}"
        return "\n".join(files) if files else "(empty)"

    return [
        ToolDefinition(
            name="read_file",
            description="Read a file from the shared workspace (relative paths only).",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            callable=read_file,
            is_async=False,
        ),
        ToolDefinition(
            name="write_file",
            description="Write a file in the shared workspace (relative paths, max 10MB).",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            callable=write_file,
            is_async=False,
        ),
        ToolDefinition(
            name="list_files",
            description="List files in the shared workspace (optionally under a subdir).",
            parameters={
                "type": "object",
                "properties": {"subdir": {"type": "string"}},
            },
            callable=list_files,
            is_async=False,
        ),
    ]


__all__ = ["make_workspace_tools"]
