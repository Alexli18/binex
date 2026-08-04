"""Shared workflow-discovery service.

Used by ``binex list``, the Web UI workflows API, and the MCP server so that
all callers produce identical results from the same code path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

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


def get_examples_dir() -> Path | None:
    """Return the built-in ``examples/`` directory from the binex package.

    Works both in development (repo root) and when installed as a package.
    """
    # Development layout: src/binex/workflow_spec/discovery.py → repo root
    pkg_root = Path(__file__).resolve().parent.parent.parent.parent
    examples = pkg_root / "examples"
    if examples.is_dir():
        return examples

    # Installed layout: site-packages/binex/… → look via package __file__
    try:
        import binex  # noqa: PLC0415

        installed_root = Path(binex.__file__).resolve().parent.parent.parent
        examples = installed_root / "examples"
        if examples.is_dir():
            return examples
    except Exception:
        pass

    return None


def _is_workflow_yaml(path: Path) -> bool:
    """Return True when the file contains a ``nodes:`` top-level key."""
    try:
        text = path.read_text(errors="ignore")
        return "\nnodes:" in text or text.startswith("nodes:")
    except OSError:
        return False


def scan_workflow_files(base: Path) -> list[str]:
    """Return relative paths (strings) of workflow YAML files under *base*.

    Excludes directories in ``_EXCLUDED_DIRS`` and dotfiles.  Results are
    sorted for determinism.
    """
    workflows: list[str] = []
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


def scan_workflow_details(directory: Path) -> list[dict[str, Any]]:
    """Return rich workflow dicts (path, name, description, nodes count).

    Parses YAML to extract metadata.  Invalid files are skipped silently.
    """
    results: list[dict[str, Any]] = []
    if not directory.is_dir():
        return results
    for p in sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml")):
        try:
            data = yaml.safe_load(p.read_text())
            if isinstance(data, dict) and "nodes" in data:
                results.append(
                    {
                        "path": str(p),
                        "name": data.get("name", p.stem),
                        "description": data.get("description", ""),
                        "nodes": len(data.get("nodes", {})),
                    }
                )
        except Exception:  # noqa: BLE001
            continue
    return results


def list_workflows(base: Path | None = None) -> dict[str, list[str]]:
    """Return ``{"workflows": [...]}`` using the same logic as ``binex list``.

    When *base* is ``None`` the current working directory is used.  Falls back
    to the built-in examples when no workflows are found in *base*.

    This is the canonical function used by the CLI, REST API, and MCP server.
    """
    if base is None:
        base = Path.cwd()

    workflows = scan_workflow_files(base)

    if not workflows:
        examples_dir = get_examples_dir()
        if examples_dir:
            for rel in scan_workflow_files(examples_dir):
                workflows.append(f"examples/{rel}")

    return {"workflows": workflows}


def resolve_workflow_path(path: str, base: Path | None = None) -> Path | None:
    """Resolve a workflow path string to an absolute ``Path``.

    Checks *base* (default: cwd) first, then the built-in examples directory.
    Returns ``None`` when the file cannot be found within an allowed root.
    """
    if base is None:
        base = Path.cwd()

    resolved = (base / path).resolve()
    if str(resolved).startswith(str(base.resolve())) and resolved.exists():
        return resolved

    # Built-in examples: path may be "examples/simple.yaml"
    examples_dir = get_examples_dir()
    if examples_dir and path.startswith("examples/"):
        rel = path[len("examples/"):]
        resolved = (examples_dir / rel).resolve()
        if (
            str(resolved).startswith(str(examples_dir.resolve()))
            and resolved.exists()
        ):
            return resolved

    return None
