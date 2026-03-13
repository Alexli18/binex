"""Tests for the plugin registry — discovery, resolution, inline loading, conflicts."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from binex.plugins import PluginMetadata, PluginRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeAdapter:
    """Stub adapter returned by fake plugins."""

    def __init__(self, uri: str, config: dict):
        self.uri = uri
        self.config = config


class _FakePlugin:
    """Stub plugin class with create_adapter()."""

    prefix = "fakeplugin"

    def create_adapter(self, uri: str, config: dict):
        return _FakeAdapter(uri, config)


def _make_entry_point(name: str, value: str, *, pkg: str = "binex-fake", version: str = "1.0.0"):
    """Create a mock entry point."""
    ep = MagicMock()
    ep.name = name
    ep.value = value
    ep.dist = MagicMock()
    ep.dist.name = pkg
    ep.dist.version = version
    ep.load.return_value = _FakePlugin
    return ep


# ---------------------------------------------------------------------------
# T009: discover() tests
# ---------------------------------------------------------------------------

class TestDiscover:
    def test_discovers_entry_points_without_importing(self):
        ep = _make_entry_point("fakeplugin", "binex_fake:FakePlugin")
        registry = PluginRegistry()

        with patch("binex.plugins.entry_points", return_value=[ep]):
            result = registry.discover()

        assert len(result) == 1
        assert result[0].prefix == "fakeplugin"
        assert result[0].package_name == "binex-fake"
        assert result[0].version == "1.0.0"
        assert result[0].source == "entry_point"
        # Entry point NOT loaded during discover
        ep.load.assert_not_called()

    def test_stores_metadata_correctly(self):
        ep = _make_entry_point("myplugin", "my_pkg:MyPlugin", pkg="binex-myplugin", version="2.3.0")
        registry = PluginRegistry()

        with patch("binex.plugins.entry_points", return_value=[ep]):
            registry.discover()

        plugins = registry.all_plugins()
        assert len(plugins) == 1
        assert plugins[0]["prefix"] == "myplugin"
        assert plugins[0]["package_name"] == "binex-myplugin"
        assert plugins[0]["version"] == "2.3.0"

    def test_returns_empty_when_no_plugins(self):
        registry = PluginRegistry()
        with patch("binex.plugins.entry_points", return_value=[]):
            result = registry.discover()

        assert result == []
        assert registry.all_plugins() == []

    def test_skips_corrupt_entry_point_gracefully(self):
        """Corrupt entry point is skipped with warning, valid ones are kept."""
        good_ep = _make_entry_point("good", "good_pkg:Good")
        bad_ep = MagicMock()
        bad_ep.name = property(lambda s: (_ for _ in ()).throw(RuntimeError("corrupt")))
        # Make accessing .name raise
        type(bad_ep).name = property(lambda s: (_ for _ in ()).throw(RuntimeError("corrupt")))

        registry = PluginRegistry()
        import warnings
        with patch("binex.plugins.entry_points", return_value=[bad_ep, good_ep]):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                result = registry.discover()

        assert len(result) == 1
        assert result[0].prefix == "good"
        assert len(w) == 1
        assert "corrupt" in str(w[0].message)


# ---------------------------------------------------------------------------
# T010: resolve() tests
# ---------------------------------------------------------------------------

class TestResolve:
    def _setup_registry(self):
        ep = _make_entry_point("fakeplugin", "binex_fake:FakePlugin")
        registry = PluginRegistry()
        with patch("binex.plugins.entry_points", return_value=[ep]):
            registry.discover()
        # Wire up the entry point for lazy loading
        registry._entry_points["fakeplugin"] = ep
        return registry, ep

    def test_resolves_known_prefix_to_adapter(self):
        registry, ep = self._setup_registry()
        adapter = registry.resolve("fakeplugin://my-chain", {"temperature": 0.5})

        assert isinstance(adapter, _FakeAdapter)
        assert adapter.uri == "my-chain"
        assert adapter.config == {"temperature": 0.5}

    def test_lazy_loads_on_first_call_only(self):
        registry, ep = self._setup_registry()

        registry.resolve("fakeplugin://a", {})
        registry.resolve("fakeplugin://b", {})

        # load() called exactly once (lazy + cached)
        ep.load.assert_called_once()

    def test_caches_instance_on_repeat_calls(self):
        registry, ep = self._setup_registry()

        registry.resolve("fakeplugin://a", {})
        assert "fakeplugin" in registry._instances

        registry.resolve("fakeplugin://b", {})
        # Still the same instance
        assert ep.load.call_count == 1

    def test_returns_none_for_unknown_prefix(self):
        registry, _ = self._setup_registry()
        result = registry.resolve("unknown://thing", {})
        assert result is None

    def test_wraps_import_errors_with_context(self):
        ep = _make_entry_point("badplugin", "bad_pkg:Bad")
        ep.load.side_effect = ImportError("No module named 'bad_pkg'")
        registry = PluginRegistry()
        with patch("binex.plugins.entry_points", return_value=[ep]):
            registry.discover()
        registry._entry_points["badplugin"] = ep

        with pytest.raises(RuntimeError, match="Plugin 'badplugin' failed to load"):
            registry.resolve("badplugin://x", {})


# ---------------------------------------------------------------------------
# T011: Integration tests — adapter_registry plugin fallback
# ---------------------------------------------------------------------------

class TestAdapterRegistryPluginFallback:
    def test_builtin_adapters_still_work(self):
        """Built-in adapters (local://, llm://) are unaffected by plugin system."""
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.models.workflow import NodeSpec, WorkflowSpec
        from binex.runtime.dispatcher import Dispatcher

        spec = WorkflowSpec(
            name="test",
            nodes={
                "a": NodeSpec(id="a", agent="local://handler", outputs=["r"]),
            },
        )
        dispatcher = Dispatcher()
        registry = PluginRegistry()
        with patch("binex.plugins.entry_points", return_value=[]):
            registry.discover()

        register_workflow_adapters(dispatcher, spec, plugin_registry=registry)
        assert "local://handler" in dispatcher._adapters

    def test_unknown_prefix_falls_through_to_plugin(self):
        """Unknown prefix resolved via plugin registry."""
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.models.workflow import NodeSpec, WorkflowSpec
        from binex.runtime.dispatcher import Dispatcher

        spec = WorkflowSpec(
            name="test",
            nodes={
                "a": NodeSpec(id="a", agent="fakeplugin://chain", outputs=["r"]),
            },
        )
        dispatcher = Dispatcher()

        ep = _make_entry_point("fakeplugin", "binex_fake:FakePlugin")
        registry = PluginRegistry()
        with patch("binex.plugins.entry_points", return_value=[ep]):
            registry.discover()
        registry._entry_points["fakeplugin"] = ep

        register_workflow_adapters(dispatcher, spec, plugin_registry=registry)
        assert "fakeplugin://chain" in dispatcher._adapters

    def test_error_when_no_adapter_and_no_plugin(self):
        """Clear error when no built-in or plugin adapter matches."""
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.models.workflow import NodeSpec, WorkflowSpec
        from binex.runtime.dispatcher import Dispatcher

        spec = WorkflowSpec(
            name="test",
            nodes={
                "a": NodeSpec(id="a", agent="nonexistent://x", outputs=["r"]),
            },
        )
        dispatcher = Dispatcher()
        registry = PluginRegistry()
        with patch("binex.plugins.entry_points", return_value=[]):
            registry.discover()

        with pytest.raises(ValueError, match="No adapter found for 'nonexistent://x'"):
            register_workflow_adapters(dispatcher, spec, plugin_registry=registry)


# ---------------------------------------------------------------------------
# T013: resolve_inline() tests
# ---------------------------------------------------------------------------

class TestResolveInline:
    def test_loads_class_via_importlib(self):
        registry = PluginRegistry()
        # Use the _FakePlugin from this very module
        adapter = registry.resolve_inline(
            f"{__name__}._FakePlugin", "fakeplugin://my-chain", {"key": "val"},
        )
        assert isinstance(adapter, _FakeAdapter)
        assert adapter.uri == "my-chain"
        assert adapter.config == {"key": "val"}

    def test_validates_create_adapter_exists(self):
        registry = PluginRegistry()
        # dataclass has no create_adapter()
        with pytest.raises(ValueError, match="missing create_adapter\\(\\) method"):
            registry.resolve_inline(
                f"{__name__}.PluginMetadata", "x://y", {},
            )

    def test_error_on_missing_module(self):
        registry = PluginRegistry()
        with pytest.raises(ValueError, match="Cannot import adapter_class"):
            registry.resolve_inline("nonexistent_pkg.Foo", "x://y", {})

    def test_error_on_missing_class_in_module(self):
        registry = PluginRegistry()
        with pytest.raises(ValueError, match="has no attribute 'NoSuchClass'"):
            registry.resolve_inline(f"{__name__}.NoSuchClass", "x://y", {})

    def test_error_message_includes_dotted_path(self):
        registry = PluginRegistry()
        with pytest.raises(ValueError, match="no_such_module.BadClass"):
            registry.resolve_inline("no_such_module.BadClass", "x://y", {})

    def test_error_on_non_dotted_path(self):
        registry = PluginRegistry()
        with pytest.raises(ValueError, match="expected dotted path"):
            registry.resolve_inline("NoDots", "x://y", {})


# ---------------------------------------------------------------------------
# T014: Inline priority over entry point plugin
# ---------------------------------------------------------------------------

class TestInlinePriority:
    def test_inline_adapter_class_takes_priority_over_entry_point(self):
        """When adapter_class is in node config, it takes priority over installed plugin."""
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.models.workflow import NodeSpec, WorkflowSpec
        from binex.runtime.dispatcher import Dispatcher

        spec = WorkflowSpec(
            name="test",
            nodes={
                "a": NodeSpec(
                    id="a",
                    agent="fakeplugin://chain",
                    outputs=["r"],
                    config={"adapter_class": f"{__name__}._FakePlugin"},
                ),
            },
        )
        dispatcher = Dispatcher()

        # Set up registry with an entry point for the same prefix
        ep = _make_entry_point("fakeplugin", "binex_fake:FakePlugin")
        registry = PluginRegistry()
        with patch("binex.plugins.entry_points", return_value=[ep]):
            registry.discover()
        registry._entry_points["fakeplugin"] = ep

        register_workflow_adapters(dispatcher, spec, plugin_registry=registry)
        assert "fakeplugin://chain" in dispatcher._adapters
        # Entry point should NOT have been loaded (inline took priority)
        ep.load.assert_not_called()


# ---------------------------------------------------------------------------
# T020: Conflict detection tests
# ---------------------------------------------------------------------------

class TestConflictDetection:
    def test_plugin_with_builtin_prefix_raises(self):
        """Plugin claiming builtin prefix 'llm' raises ValueError."""
        ep = _make_entry_point("llm", "bad_pkg:Bad", pkg="binex-bad")
        registry = PluginRegistry()

        with patch("binex.plugins.entry_points", return_value=[ep]):
            with pytest.raises(ValueError, match="cannot use prefix 'llm'.*reserved for the built-in llm adapter"):
                registry.discover()

    def test_two_plugins_same_prefix_raises(self):
        """Two plugins claiming same prefix raises ValueError with both package names."""
        ep1 = _make_entry_point("custom", "pkg1:P1", pkg="binex-custom-a")
        ep2 = _make_entry_point("custom", "pkg2:P2", pkg="binex-custom-b")
        registry = PluginRegistry()

        with patch("binex.plugins.entry_points", return_value=[ep1, ep2]):
            with pytest.raises(ValueError, match="both claim prefix 'custom'"):
                registry.discover()

    def test_valid_non_conflicting_plugins_pass(self):
        """Multiple plugins with different non-builtin prefixes pass discovery."""
        ep1 = _make_entry_point("alpha", "pkg1:A", pkg="binex-alpha")
        ep2 = _make_entry_point("beta", "pkg2:B", pkg="binex-beta")
        registry = PluginRegistry()

        with patch("binex.plugins.entry_points", return_value=[ep1, ep2]):
            result = registry.discover()

        assert len(result) == 2
        prefixes = {m.prefix for m in result}
        assert prefixes == {"alpha", "beta"}

    def test_builtin_conflict_error_names_plugin_and_builtin(self):
        """Error message includes plugin package name and built-in adapter name."""
        ep = _make_entry_point("a2a", "rogue:Rogue", pkg="binex-rogue")
        registry = PluginRegistry()

        with patch("binex.plugins.entry_points", return_value=[ep]):
            with pytest.raises(ValueError) as exc_info:
                registry.discover()

        msg = str(exc_info.value)
        assert "binex-rogue" in msg
        assert "a2a" in msg
        assert "built-in" in msg

    def test_duplicate_prefix_error_names_both_packages(self):
        """Error message includes both conflicting package names."""
        ep1 = _make_entry_point("dup", "pkg1:P1", pkg="binex-first")
        ep2 = _make_entry_point("dup", "pkg2:P2", pkg="binex-second")
        registry = PluginRegistry()

        with patch("binex.plugins.entry_points", return_value=[ep1, ep2]):
            with pytest.raises(ValueError) as exc_info:
                registry.discover()

        msg = str(exc_info.value)
        assert "binex-first" in msg
        assert "binex-second" in msg
