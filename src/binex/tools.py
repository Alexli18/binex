"""Tool calling support — @tool decorator, schema generation, and tool loading."""

from __future__ import annotations

import importlib
import inspect
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, get_type_hints


@dataclass
class ToolDefinition:
    """Runtime representation of a tool available to an LLM agent."""

    name: str
    description: str
    parameters: dict[str, Any]
    callable: Callable[..., Any] | None = None
    is_async: bool = False

    def to_openai_schema(self) -> dict[str, Any]:
        """Return an OpenAI-compatible tool schema dict."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ---------------------------------------------------------------------------
# Type mapping for schema generation
# ---------------------------------------------------------------------------

_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


# ---------------------------------------------------------------------------
# @tool decorator
# ---------------------------------------------------------------------------

def tool(
    fn: Callable[..., Any] | None = None,
    *,
    description: str | None = None,
    name: str | None = None,
    parameter_descriptions: dict[str, str] | None = None,
) -> Any:
    """Decorator that marks a function as a Binex tool.

    Can be used bare (``@tool``) or with arguments
    (``@tool(description="...")``).
    """

    def _wrap(func: Callable[..., Any]) -> Callable[..., Any]:
        func._binex_tool = {  # type: ignore[attr-defined]
            "name": name,
            "description": description,
            "parameter_descriptions": parameter_descriptions,
        }
        return func

    if fn is not None:
        # Bare @tool without arguments
        return _wrap(fn)
    return _wrap


# ---------------------------------------------------------------------------
# Schema generation
# ---------------------------------------------------------------------------

def _build_param_property(
    param_name: str,
    param: inspect.Parameter,
    hints: dict[str, Any],
    param_descs: dict[str, str],
) -> tuple[dict[str, Any], bool]:
    """Build a single JSON Schema property for a function parameter.

    Returns ``(property_dict, is_required)``.
    """
    prop: dict[str, Any] = {}
    hint = hints.get(param_name)
    if hint and hint in _TYPE_MAP:
        prop["type"] = _TYPE_MAP[hint]
    else:
        prop["type"] = "string"
    if param_name in param_descs:
        prop["description"] = param_descs[param_name]
    is_required = param.default is inspect.Parameter.empty
    return prop, is_required


def build_tool_schema(func: Callable[..., Any]) -> dict[str, Any]:
    """Generate an OpenAI-compatible function schema from a Python function.

    Uses type hints, docstring, and optional ``@tool`` metadata.
    """
    meta: dict[str, Any] = getattr(func, "_binex_tool", {})
    func_name = meta.get("name") or func.__name__
    func_desc = meta.get("description") or (func.__doc__ or "").strip().split("\n")[0] or func_name
    param_descs: dict[str, str] = meta.get("parameter_descriptions") or {}

    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        prop, is_required = _build_param_property(param_name, param, hints, param_descs)
        properties[param_name] = prop
        if is_required:
            required.append(param_name)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return {
        "type": "function",
        "function": {
            "name": func_name,
            "description": func_desc,
            "parameters": schema,
        },
    }


# ---------------------------------------------------------------------------
# Tool loading
# ---------------------------------------------------------------------------

def load_python_tool(uri: str, workflow_dir: str | None = None) -> ToolDefinition:
    """Load a tool from a ``python://module.function`` URI.

    If *workflow_dir* is provided it is temporarily added to ``sys.path``
    so that project-local modules can be imported.
    """
    if not uri.startswith("python://"):
        raise ValueError(f"Invalid tool URI: {uri!r} (must start with 'python://')")

    path_part = uri[len("python://"):]
    last_dot = path_part.rfind(".")
    if last_dot == -1:
        raise ValueError(f"Invalid tool URI: {uri!r} (must be python://module.function)")

    module_path = path_part[:last_dot]
    func_name = path_part[last_dot + 1:]

    added_to_path = False
    if workflow_dir and workflow_dir not in sys.path:
        sys.path.insert(0, workflow_dir)
        added_to_path = True

    try:
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ImportError(
                f"Cannot import module '{module_path}' for tool '{uri}'"
            ) from exc

        func = getattr(module, func_name, None)
        if func is None:
            raise AttributeError(
                f"Module '{module_path}' has no function '{func_name}'"
            )
        if not callable(func):
            raise TypeError(
                f"'{func_name}' in '{module_path}' is not callable"
            )

        schema = build_tool_schema(func)
        fn_schema = schema["function"]

        return ToolDefinition(
            name=fn_schema["name"],
            description=fn_schema["description"],
            parameters=fn_schema["parameters"],
            callable=func,
            is_async=inspect.iscoroutinefunction(func),
        )
    finally:
        if added_to_path and workflow_dir in sys.path:
            sys.path.remove(workflow_dir)


def _resolve_inline_tool(tool_dict: dict[str, Any]) -> ToolDefinition:
    """Resolve an inline tool definition dict to a ToolDefinition."""
    name = tool_dict.get("name", "unnamed_tool")
    description = tool_dict.get("description", name)
    raw_params = tool_dict.get("parameters", {})

    # Convert simplified YAML params to JSON Schema
    properties: dict[str, Any] = {}
    required: list[str] = []
    for pname, pspec in raw_params.items():
        if isinstance(pspec, dict):
            properties[pname] = pspec
        else:
            properties[pname] = {"type": "string"}
        required.append(pname)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return ToolDefinition(
        name=name,
        description=description,
        parameters=schema,
        callable=None,
        is_async=False,
    )


def resolve_tools(
    tools_spec: list[str | dict[str, Any]],
    workflow_dir: str | None = None,
) -> list[ToolDefinition]:
    """Resolve a list of tool specs (URIs or inline dicts) to ToolDefinitions."""
    result: list[ToolDefinition] = []
    for spec in tools_spec:
        if isinstance(spec, str):
            if spec.startswith("python://"):
                result.append(load_python_tool(spec, workflow_dir=workflow_dir))
            else:
                raise ValueError(f"Unsupported tool URI scheme: {spec!r}")
        elif isinstance(spec, dict):
            result.append(_resolve_inline_tool(spec))
        else:
            raise TypeError(f"Invalid tool spec type: {type(spec)}")
    return result


async def execute_tool_call(
    tool_def: ToolDefinition,
    arguments: dict[str, Any],
) -> str:
    """Execute a tool call and return the result as a string."""
    if tool_def.callable is None:
        return (
            f"Error: Tool '{tool_def.name}' has no handler function. "
            f"Define it via python:// URI."
        )

    try:
        if tool_def.is_async:
            result = await tool_def.callable(**arguments)
        else:
            result = tool_def.callable(**arguments)
        return str(result)
    except Exception as exc:
        return f"Error executing tool '{tool_def.name}': {exc}"


__all__ = [
    "ToolDefinition",
    "build_tool_schema",
    "execute_tool_call",
    "load_python_tool",
    "resolve_tools",
    "tool",
]
