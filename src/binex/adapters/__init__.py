"""Agent adapters — pluggable backends for task execution."""

from binex.adapters.base import AgentAdapter
from binex.adapters.local import LocalPythonAdapter

__all__ = ["AgentAdapter", "LocalPythonAdapter"]
