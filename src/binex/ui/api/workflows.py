"""Workflows API endpoints for Binex Web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from binex.ui.api.errors import APIError
from binex.workflow_spec.discovery import list_workflows as _list_workflows
from binex.workflow_spec.discovery import resolve_workflow_path as _resolve_workflow_path_svc

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _get_workflows_dir() -> Path:
    """Return the base directory for workflow files. Extracted for test patching."""
    return Path.cwd()


@router.get("")
async def list_workflows() -> JSONResponse:
    """List workflow YAML files in the working directory.

    Falls back to built-in examples if no workflows found in cwd.
    """
    result = _list_workflows(base=_get_workflows_dir())
    return JSONResponse(result)


def _resolve_workflow_path(path: str) -> Path | None:
    """Resolve a workflow path, checking cwd first then built-in examples."""
    return _resolve_workflow_path_svc(path, base=_get_workflows_dir())


@router.get("/{path:path}")
async def get_workflow(path: str) -> JSONResponse:
    """Get the content of a specific workflow file."""
    resolved = _resolve_workflow_path(path)
    if resolved is None:
        raise APIError(
            404, "workflow_not_found",
            f"Workflow '{path}' not found",
        )
    content = resolved.read_text()
    return JSONResponse({"path": path, "content": content})


class SaveWorkflowRequest(BaseModel):
    content: str


@router.put("/{path:path}")
async def save_workflow(path: str, body: SaveWorkflowRequest) -> JSONResponse:
    """Save content to a specific workflow file."""
    base = _get_workflows_dir()
    # Path traversal protection
    resolved = (base / path).resolve()
    if not str(resolved).startswith(str(base.resolve())):
        raise APIError(
            400, "path_traversal",
            "Path traversal not allowed",
        )
    # Ensure parent directories exist
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(body.content)
    return JSONResponse({"path": path, "saved": True})
