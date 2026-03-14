"""Workflows API endpoints for Binex Web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _get_workflows_dir() -> Path:
    """Return the base directory for workflow files. Extracted for test patching."""
    return Path.cwd()


_EXCLUDED_DIRS = {
    "node_modules",
    ".binex",
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "ui",
    "docker",
    "src",
    ".specify",
    "specs",
}


def _is_workflow_yaml(path: Path) -> bool:
    """Check if a YAML file looks like a Binex workflow (has 'nodes:' key)."""
    try:
        text = path.read_text(errors="ignore")
        return "\nnodes:" in text or text.startswith("nodes:")
    except OSError:
        return False


def _scan_workflows(base: Path) -> list[str]:
    """Scan a directory for workflow YAML files."""
    workflows = []
    for p in sorted(base.rglob("*.yaml")):
        rel = str(p.relative_to(base))
        if rel.startswith("."):
            continue
        top_dir = rel.split("/")[0] if "/" in rel else None
        if top_dir in _EXCLUDED_DIRS:
            continue
        if _is_workflow_yaml(p):
            workflows.append(rel)
    return workflows


def _get_examples_dir() -> Path | None:
    """Return the built-in examples directory from the binex package."""
    try:
        import binex
        pkg_root = Path(binex.__file__).resolve().parent.parent.parent
        examples = pkg_root / "examples"
        if examples.is_dir():
            return examples
    except Exception:
        pass
    return None


@router.get("")
async def list_workflows() -> JSONResponse:
    """List workflow YAML files in the working directory.

    Falls back to built-in examples if no workflows found in cwd.
    """
    base = _get_workflows_dir()
    workflows = _scan_workflows(base)

    # Fallback: include built-in examples if cwd has no workflows
    if not workflows:
        examples_dir = _get_examples_dir()
        if examples_dir:
            for rel in _scan_workflows(examples_dir):
                workflows.append(f"examples/{rel}")

    return JSONResponse({"workflows": workflows})


def _resolve_workflow_path(path: str) -> Path | None:
    """Resolve a workflow path, checking cwd first then built-in examples."""
    base = _get_workflows_dir()
    resolved = (base / path).resolve()
    if str(resolved).startswith(str(base.resolve())) and resolved.exists():
        return resolved

    # Try built-in examples (e.g. path = "examples/simple.yaml")
    examples_dir = _get_examples_dir()
    if examples_dir and path.startswith("examples/"):
        rel = path[len("examples/"):]
        resolved = (examples_dir / rel).resolve()
        if str(resolved).startswith(str(examples_dir.resolve())) and resolved.exists():
            return resolved

    return None


@router.get("/{path:path}")
async def get_workflow(path: str) -> JSONResponse:
    """Get the content of a specific workflow file."""
    resolved = _resolve_workflow_path(path)
    if resolved is None:
        return JSONResponse(
            status_code=404, content={"error": f"Workflow '{path}' not found"}
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
        return JSONResponse(
            status_code=400, content={"error": "Path traversal not allowed"}
        )
    # Ensure parent directories exist
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(body.content)
    return JSONResponse({"path": path, "saved": True})
