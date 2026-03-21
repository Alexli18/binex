"""Built-in tools registry — 10 tools with safe defaults."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from binex.tools._core import ToolDefinition, build_tool_schema, tool

_BUILTIN_REGISTRY: dict[str, ToolDefinition] = {}


def register_builtin(tool_def: ToolDefinition) -> None:
    """Register a built-in tool."""
    _BUILTIN_REGISTRY[tool_def.name] = tool_def


def get_builtin(name: str) -> ToolDefinition:
    """Get a built-in tool by name. Raises ValueError if not found."""
    if name not in _BUILTIN_REGISTRY:
        raise ValueError(
            f"Unknown built-in tool: '{name}'. "
            f"Available: {', '.join(sorted(_BUILTIN_REGISTRY))}"
        )
    return _BUILTIN_REGISTRY[name]


def list_builtins() -> list[str]:
    """Return sorted list of available built-in tool names."""
    return sorted(_BUILTIN_REGISTRY)


def _register_tool(func: Callable[..., Any]) -> None:
    """Helper to register a @tool-decorated function."""
    schema = build_tool_schema(func)
    fn_schema = schema["function"]
    register_builtin(ToolDefinition(
        name=fn_schema["name"],
        description=fn_schema["description"],
        parameters=fn_schema["parameters"],
        callable=func,
        is_async=inspect.iscoroutinefunction(func),
    ))


# ---------------------------------------------------------------------------
# 1. calculator — safe math evaluation
# ---------------------------------------------------------------------------

@tool(description="Evaluate a mathematical expression safely (supports math functions)")
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression safely."""
    import math

    allowed = {
        k: v for k, v in math.__dict__.items()
        if not k.startswith("_")
    }
    allowed["abs"] = abs
    allowed["round"] = round
    allowed["min"] = min
    allowed["max"] = max
    try:
        result = eval(expression, {"__builtins__": {}}, allowed)  # noqa: S307
        return str(result)
    except Exception as exc:
        return f"Error: {exc}"


# ---------------------------------------------------------------------------
# 2. dice_roll — D&D dice notation (NdM+K)
# ---------------------------------------------------------------------------

@tool(description="Roll dice using D&D notation (e.g. 2d6+3, 1d20, 4d6)")
def dice_roll(notation: str) -> str:
    """Roll dice using NdM+K notation."""
    import random
    import re

    match = re.fullmatch(r"(\d+)d(\d+)([+-]\d+)?", notation.strip().lower())
    if not match:
        return f"Error: invalid dice notation '{notation}'. Use format NdM or NdM+K (e.g. 2d6+3)"

    count = int(match.group(1))
    sides = int(match.group(2))
    modifier = int(match.group(3)) if match.group(3) else 0

    if count < 1 or count > 100:
        return "Error: dice count must be 1-100"
    if sides < 2 or sides > 1000:
        return "Error: dice sides must be 2-1000"

    rolls = [random.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier

    mod_str = f"{modifier:+d}" if modifier else ""
    return f"{notation}: [{', '.join(str(r) for r in rolls)}]{mod_str} = {total}"


# ---------------------------------------------------------------------------
# 3. fetch_url — async HTTP GET
# ---------------------------------------------------------------------------

@tool(description="Fetch contents of a URL via HTTP GET")
async def fetch_url(url: str) -> str:
    """Fetch URL contents."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text
            if len(text) > 50_000:
                text = text[:50_000] + "\n...(truncated to 50KB)"
            return text
    except Exception as exc:
        return f"Error fetching {url}: {exc}"


# ---------------------------------------------------------------------------
# 4. http_request — async HTTP with method
# ---------------------------------------------------------------------------

@tool(description="Make an HTTP request (GET/POST/PUT/DELETE)")
async def http_request(url: str, method: str = "GET", body: str = "") -> str:
    """Make an HTTP request."""
    import httpx

    method = method.upper()
    if method not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
        return f"Error: unsupported method '{method}'"

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            kwargs: dict[str, Any] = {"method": method, "url": url}
            if body and method in ("POST", "PUT", "PATCH"):
                kwargs["content"] = body
                kwargs["headers"] = {"Content-Type": "application/json"}
            resp = await client.request(**kwargs)
            text = resp.text
            if len(text) > 50_000:
                text = text[:50_000] + "\n...(truncated to 50KB)"
            return f"HTTP {resp.status_code}\n{text}"
    except Exception as exc:
        return f"Error: {exc}"


# ---------------------------------------------------------------------------
# 5. web_search — async web search via DuckDuckGo HTML
# ---------------------------------------------------------------------------

@tool(description="Search the web and return results")
async def web_search(query: str) -> str:
    """Search the web using DuckDuckGo."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Binex/1.0"},
            )
            resp.raise_for_status()
            text = resp.text
            if len(text) > 50_000:
                text = text[:50_000]
            return text
    except Exception as exc:
        return f"Error searching: {exc}"


# ---------------------------------------------------------------------------
# 6. read_file — sandbox: relative paths only
# ---------------------------------------------------------------------------

@tool(description="Read file contents (workflow directory only, relative paths)")
def read_file(path: str) -> str:
    """Read a file. Only relative paths within the working directory are allowed."""
    from pathlib import Path

    if ".." in path:
        return "Error: path traversal ('..') not allowed"

    p = Path(path)
    if p.is_absolute():
        return "Error: absolute paths not allowed, use relative paths only"

    try:
        resolved = p.resolve()
        cwd = Path.cwd().resolve()
        if not str(resolved).startswith(str(cwd)):
            return "Error: path resolves outside working directory"
        return resolved.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except Exception as exc:
        return f"Error reading {path}: {exc}"


# ---------------------------------------------------------------------------
# 7. write_file — sandbox: relative paths only, max 10MB
# ---------------------------------------------------------------------------

@tool(description="Write content to a file (workflow directory only, max 10MB)")
def write_file(path: str, content: str) -> str:
    """Write to a file. Only relative paths, max 10MB."""
    from pathlib import Path

    if ".." in path:
        return "Error: path traversal ('..') not allowed"

    p = Path(path)
    if p.is_absolute():
        return "Error: absolute paths not allowed, use relative paths only"

    max_size = 10 * 1024 * 1024
    if len(content) > max_size:
        return f"Error: content exceeds max file size (10MB), got {len(content)} bytes"

    try:
        resolved = p.resolve()
        cwd = Path.cwd().resolve()
        if not str(resolved).startswith(str(cwd)):
            return "Error: path resolves outside working directory"
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return f"Written {len(content)} bytes to {path}"
    except Exception as exc:
        return f"Error writing {path}: {exc}"


# ---------------------------------------------------------------------------
# 8. shell_command — subprocess with timeout and output limit
# ---------------------------------------------------------------------------

@tool(description="Execute a shell command (timeout 30s, max output 10KB)")
def shell_command(command: str) -> str:
    """Execute a shell command with safety constraints."""
    import subprocess

    try:
        result = subprocess.run(
            command,
            shell=True,  # noqa: S602
            capture_output=True,
            text=True,
            timeout=30,
            cwd=".",
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"

        max_output = 10 * 1024
        if len(output) > max_output:
            output = output[:max_output] + "\n...(truncated to 10KB)"

        if result.returncode != 0:
            return f"Exit code: {result.returncode}\n{output}"
        return output if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30 seconds"
    except Exception as exc:
        return f"Error: {exc}"


# ---------------------------------------------------------------------------
# 9. json_parse — parse JSON and extract fields
# ---------------------------------------------------------------------------

@tool(description="Parse JSON string and extract specified fields (comma-separated)")
def json_parse(json_string: str, fields: str = "") -> str:
    """Parse JSON and optionally extract fields."""
    import json

    try:
        data = json.loads(json_string)
    except json.JSONDecodeError as exc:
        return f"Error: invalid JSON — {exc}"

    if not fields.strip():
        return json.dumps(data, indent=2, ensure_ascii=False)

    result = {}
    for field in fields.split(","):
        field = field.strip()
        if not field:
            continue
        if isinstance(data, dict) and field in data:
            result[field] = data[field]
        else:
            result[field] = None

    if not result:
        return "No matching fields found"
    return json.dumps(result, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 10. random_choice — pick from comma-separated list
# ---------------------------------------------------------------------------

@tool(description="Pick a random item from a comma-separated list")
def random_choice(options: str) -> str:
    """Pick a random item from a comma-separated list."""
    import random

    items = [item.strip() for item in options.split(",") if item.strip()]
    if not items:
        return "Error: no options provided"
    return random.choice(items)


# ---------------------------------------------------------------------------
# Auto-register all tools
# ---------------------------------------------------------------------------

_register_tool(calculator)
_register_tool(dice_roll)
_register_tool(fetch_url)
_register_tool(http_request)
_register_tool(web_search)
_register_tool(read_file)
_register_tool(write_file)
_register_tool(shell_command)
_register_tool(json_parse)
_register_tool(random_choice)
