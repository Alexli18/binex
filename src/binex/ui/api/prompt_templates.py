"""Prompt templates API — list, read, create, update, delete."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/prompts", tags=["prompts-templates"])

# Category prefix ↔ display name mapping (bidirectional).
CATEGORY_MAP: dict[str, str] = {
    "biz": "Business",
    "cnt": "Content",
    "dat": "Data",
    "dev": "Development",
    "edu": "Education",
    "gen": "General",
    "leg": "Legal",
    "sup": "Support",
    "wf": "Workflow",
}
_CATEGORY_TO_PREFIX: dict[str, str] = {v: k for k, v in CATEGORY_MAP.items()}

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")


def _get_prompts_dir() -> Path:
    """Return the built-in prompts directory."""
    return Path(__file__).resolve().parent.parent.parent / "prompts"


def _custom_registry_path() -> Path:
    """Path to the file tracking custom prompt names."""
    return _get_prompts_dir() / ".custom-prompts"


def _load_custom_names() -> set[str]:
    """Load set of custom prompt names."""
    reg = _custom_registry_path()
    if not reg.exists():
        return set()
    return {
        line.strip()
        for line in reg.read_text().splitlines()
        if line.strip()
    }


def _save_custom_name(name: str) -> None:
    """Add a name to the custom prompts registry."""
    names = _load_custom_names()
    names.add(name)
    _custom_registry_path().write_text(
        "\n".join(sorted(names)) + "\n"
    )


def _remove_custom_name(name: str) -> None:
    """Remove a name from the custom prompts registry."""
    names = _load_custom_names()
    names.discard(name)
    if names:
        _custom_registry_path().write_text(
            "\n".join(sorted(names)) + "\n"
        )
    else:
        reg = _custom_registry_path()
        if reg.exists():
            reg.unlink()


def _category_for(name: str) -> str:
    """Derive display category from a prompt file stem."""
    prefix = name.split("-")[0] if "-" in name else "general"
    return CATEGORY_MAP.get(prefix, prefix.title())


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("/templates")
async def list_prompt_templates() -> JSONResponse:
    """List available prompt templates."""
    prompts_dir = _get_prompts_dir()
    if not prompts_dir.is_dir():
        return JSONResponse({"templates": []})

    custom_names = _load_custom_names()
    templates = []
    for f in sorted(prompts_dir.glob("*.md")):
        name = f.stem
        try:
            first_line = f.read_text().split("\n")[0].strip().lstrip("# ")
        except OSError:
            first_line = name

        templates.append({
            "name": name,
            "category": _category_for(name),
            "description": first_line,
            "is_custom": name in custom_names,
        })

    return JSONResponse({"templates": templates})


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

@router.get("/templates/{name}")
async def get_prompt_template(name: str) -> JSONResponse:
    """Get content of a specific prompt template."""
    prompts_dir = _get_prompts_dir()
    path = prompts_dir / f"{name}.md"

    resolved = path.resolve()
    if not str(resolved).startswith(str(prompts_dir.resolve())):
        return JSONResponse({"error": "Invalid path"}, status_code=400)

    if not path.exists():
        return JSONResponse(
            {"error": f"Template '{name}' not found"}, status_code=404,
        )

    content = path.read_text()
    custom_names = _load_custom_names()
    return JSONResponse({
        "name": name,
        "category": _category_for(name),
        "content": content,
        "is_custom": name in custom_names,
    })


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class CreatePromptRequest(BaseModel):
    name: str
    category: str
    content: str


@router.post("/templates")
async def create_prompt_template(body: CreatePromptRequest) -> JSONResponse:
    """Create a new prompt template."""
    if body.category not in _CATEGORY_TO_PREFIX:
        return JSONResponse(
            {"error": f"Invalid category '{body.category}'. "
             f"Allowed: {', '.join(sorted(_CATEGORY_TO_PREFIX))}"},
            status_code=422,
        )

    slug = body.name.lower().strip()
    if not _NAME_RE.match(slug):
        return JSONResponse(
            {"error": "Name must be lowercase alphanumeric with hyphens (e.g. 'my-helper')"},
            status_code=422,
        )

    prefix = _CATEGORY_TO_PREFIX[body.category]
    filename = f"{prefix}-{slug}.md"
    prompts_dir = _get_prompts_dir()
    path = prompts_dir / filename

    if path.exists():
        return JSONResponse(
            {"error": f"Template '{prefix}-{slug}' already exists"},
            status_code=409,
        )

    path.write_text(body.content)
    stem = path.stem
    _save_custom_name(stem)
    return JSONResponse(
        {"name": stem, "category": body.category, "filename": filename},
        status_code=201,
    )


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class UpdatePromptRequest(BaseModel):
    content: str


@router.put("/templates/{name}")
async def update_prompt_template(name: str, body: UpdatePromptRequest) -> JSONResponse:
    """Update content of an existing prompt template."""
    prompts_dir = _get_prompts_dir()
    path = prompts_dir / f"{name}.md"

    resolved = path.resolve()
    if not str(resolved).startswith(str(prompts_dir.resolve())):
        return JSONResponse({"error": "Invalid path"}, status_code=400)

    if not path.exists():
        return JSONResponse(
            {"error": f"Template '{name}' not found"}, status_code=404,
        )

    path.write_text(body.content)
    return JSONResponse({"name": name, "status": "updated"})


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete("/templates/{name}")
async def delete_prompt_template(name: str) -> JSONResponse:
    """Delete a prompt template."""
    prompts_dir = _get_prompts_dir()
    path = prompts_dir / f"{name}.md"

    resolved = path.resolve()
    if not str(resolved).startswith(str(prompts_dir.resolve())):
        return JSONResponse({"error": "Invalid path"}, status_code=400)

    if not path.exists():
        return JSONResponse(
            {"error": f"Template '{name}' not found"}, status_code=404,
        )

    if name not in _load_custom_names():
        return JSONResponse(
            {"error": "Cannot delete built-in prompts"},
            status_code=403,
        )

    path.unlink()
    _remove_custom_name(name)
    return JSONResponse({"name": name, "status": "deleted"})
