"""Integration tests for framework adapter plugin discovery."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from binex.adapters.langchain_adapter import LangChainPlugin
from binex.adapters.crewai_adapter import CrewAIPlugin
from binex.adapters.autogen_adapter import AutoGenPlugin
from binex.plugins import PluginRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry_point(name: str, value: str, pkg: str = "binex") -> MagicMock:
    ep = MagicMock()
    ep.name = name
    ep.value = value
    ep.dist = MagicMock()
    ep.dist.name = pkg
    ep.dist.version = "0.2.5"
    ep.load.return_value = {
        "langchain": LangChainPlugin,
        "crewai": CrewAIPlugin,
        "autogen": AutoGenPlugin,
    }[name]
    return ep


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPluginDiscovery:
    def test_all_three_prefixes_discovered(self):
        eps = [
            _make_entry_point("langchain", "binex.adapters.langchain_adapter:LangChainPlugin"),
            _make_entry_point("crewai", "binex.adapters.crewai_adapter:CrewAIPlugin"),
            _make_entry_point("autogen", "binex.adapters.autogen_adapter:AutoGenPlugin"),
        ]
        registry = PluginRegistry()
        with patch("binex.plugins.entry_points", return_value=eps):
            discovered = registry.discover()

        prefixes = {m.prefix for m in discovered}
        assert prefixes == {"langchain", "crewai", "autogen"}

    def test_plugins_appear_in_all_plugins(self):
        eps = [
            _make_entry_point("langchain", "binex.adapters.langchain_adapter:LangChainPlugin"),
            _make_entry_point("crewai", "binex.adapters.crewai_adapter:CrewAIPlugin"),
            _make_entry_point("autogen", "binex.adapters.autogen_adapter:AutoGenPlugin"),
        ]
        registry = PluginRegistry()
        with patch("binex.plugins.entry_points", return_value=eps):
            registry.discover()

        all_plugins = registry.all_plugins()
        names = {p["prefix"] for p in all_plugins}
        assert "langchain" in names
        assert "crewai" in names
        assert "autogen" in names

    def test_resolve_creates_adapter_via_plugin(self):
        eps = [
            _make_entry_point("langchain", "binex.adapters.langchain_adapter:LangChainPlugin"),
        ]
        registry = PluginRegistry()
        with patch("binex.plugins.entry_points", return_value=eps):
            registry.discover()

        with patch("importlib.util.find_spec", return_value=True):
            adapter = registry.resolve("langchain://mymod.MyChain", {})

        from binex.adapters.langchain_adapter import LangChainAdapter
        assert isinstance(adapter, LangChainAdapter)

    def test_missing_framework_raises_import_error(self):
        eps = [
            _make_entry_point("crewai", "binex.adapters.crewai_adapter:CrewAIPlugin"),
        ]
        registry = PluginRegistry()
        with patch("binex.plugins.entry_points", return_value=eps):
            registry.discover()

        with patch("importlib.util.find_spec", return_value=None):
            with pytest.raises(ImportError, match="pip install binex\\[crewai\\]"):
                registry.resolve("crewai://mymod.MyCrew", {})

    def test_no_conflict_with_builtin_prefixes(self):
        """Built-in prefixes (local, llm, human, a2a) don't conflict with framework plugins."""
        eps = [
            _make_entry_point("langchain", "binex.adapters.langchain_adapter:LangChainPlugin"),
        ]
        registry = PluginRegistry()
        with patch("binex.plugins.entry_points", return_value=eps):
            registry.discover()

        # Built-in URIs should return None (not handled by plugin system)
        assert registry.resolve("local://echo", {}) is None
        assert registry.resolve("llm://gpt-4", {}) is None

    def test_resolve_returns_none_for_unknown_prefix(self):
        eps = [
            _make_entry_point("langchain", "binex.adapters.langchain_adapter:LangChainPlugin"),
        ]
        registry = PluginRegistry()
        with patch("binex.plugins.entry_points", return_value=eps):
            registry.discover()

        assert registry.resolve("unknown://foo.bar", {}) is None
