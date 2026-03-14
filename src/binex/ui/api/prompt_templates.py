"""Prompt templates API for listing built-in prompts."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/prompts", tags=["prompts-templates"])


def _get_prompts_dir() -> Path:
    """Return the built-in prompts directory."""
    return Path(__file__).resolve().parent.parent.parent / "prompts"


@router.get("/templates")
async def list_prompt_templates() -> JSONResponse:
    """List available built-in prompt templates."""
    prompts_dir = _get_prompts_dir()
    if not prompts_dir.is_dir():
        return JSONResponse({"templates": []})

    templates = []
    for f in sorted(prompts_dir.glob("*.md")):
        name = f.stem
        # Read first line as description
        try:
            first_line = f.read_text().split("\n")[0].strip().lstrip("# ")
        except OSError:
            first_line = name

        # Categorize by prefix
        category = name.split("-")[0] if "-" in name else "general"
        category_map = {
            "biz": "Business",
            "cnt": "Content",
            "dat": "Data",
            "dev": "Development",
            "edu": "Education",
            "gen": "General",
            "leg": "Legal",
            "sup": "Support",
        }

        templates.append({
            "name": name,
            "category": category_map.get(category, category.title()),
            "description": first_line,
        })

    return JSONResponse({"templates": templates})


@router.get("/templates/{name}")
async def get_prompt_template(name: str) -> JSONResponse:
    """Get content of a specific prompt template."""
    prompts_dir = _get_prompts_dir()
    path = prompts_dir / f"{name}.md"

    # Path traversal protection
    resolved = path.resolve()
    if not str(resolved).startswith(str(prompts_dir.resolve())):
        return JSONResponse({"error": "Invalid path"}, status_code=400)

    if not path.exists():
        return JSONResponse(
            {"error": f"Template '{name}' not found"}, status_code=404
        )

    content = path.read_text()
    return JSONResponse({"name": name, "content": content})
