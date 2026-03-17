"""Built-in tools API — list available tools with metadata."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from binex.tools.builtins import get_builtin, list_builtins

router = APIRouter(prefix="/tools", tags=["tools"])

_CATEGORIES: dict[str, str] = {
    "calculator": "data",
    "dice_roll": "data",
    "json_parse": "data",
    "random_choice": "data",
    "fetch_url": "web",
    "http_request": "web",
    "web_search": "web",
    "read_file": "files",
    "write_file": "files",
    "shell_command": "system",
}


@router.get("/builtins")
async def list_builtin_tools() -> JSONResponse:
    """List all built-in tools with name, description, category."""
    tools = []
    for name in list_builtins():
        td = get_builtin(name)
        tools.append({
            "name": td.name,
            "description": td.description,
            "category": _CATEGORIES.get(td.name, "other"),
            "parameters": td.parameters,
        })
    return JSONResponse({"tools": tools})
