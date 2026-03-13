"""Plugin system for third-party and inline Binex adapters."""

from __future__ import annotations

import importlib
import warnings
from dataclasses import dataclass
from importlib.metadata import entry_points


@dataclass
class PluginMetadata:
    """Discovered plugin information (without importing the plugin class)."""

    name: str
    prefix: str
    module_path: str
    package_name: str | None = None
    version: str | None = None
    source: str = "entry_point"


class PluginRegistry:
    """Central registry for discovered and loaded plugins."""

    _builtin_prefixes: frozenset[str] = frozenset({"local", "llm", "human", "a2a"})

    def __init__(self) -> None:
        self._plugins: dict[str, PluginMetadata] = {}
        self._entry_points: dict[str, object] = {}
        self._instances: dict[str, object] = {}

    def discover(self) -> list[PluginMetadata]:
        """Scan entry points for installed plugins without importing them.

        Validates no conflicts with built-in prefixes or between plugins.
        Returns list of discovered plugin metadata.
        """
        self._instances.clear()
        eps = entry_points(group="binex.plugins")
        discovered: dict[str, tuple[PluginMetadata, object]] = {}

        for ep in eps:
            try:
                prefix = ep.name
                pkg = getattr(ep.dist, "name", None) if ep.dist else None
                ver = getattr(ep.dist, "version", None) if ep.dist else None
            except Exception as exc:
                warnings.warn(
                    f"Skipping corrupt plugin entry point: {exc}",
                    stacklevel=2,
                )
                continue

            # Check builtin conflict
            if prefix in self._builtin_prefixes:
                raise ValueError(
                    f"Plugin '{pkg or ep.value}' cannot use prefix '{prefix}' "
                    f"— it's reserved for the built-in {prefix} adapter"
                )

            # Check duplicate prefix between plugins
            if prefix in discovered:
                existing = discovered[prefix][0]
                existing_pkg = existing.package_name or existing.module_path
                raise ValueError(
                    f"Plugins '{existing_pkg}' and '{pkg or ep.value}' both claim "
                    f"prefix '{prefix}' — remove one to resolve the conflict"
                )

            meta = PluginMetadata(
                name=ep.name,
                prefix=prefix,
                module_path=ep.value,
                package_name=pkg,
                version=ver,
                source="entry_point",
            )
            discovered[prefix] = (meta, ep)

        self._plugins = {k: v[0] for k, v in discovered.items()}
        self._entry_points = {k: v[1] for k, v in discovered.items()}
        return list(self._plugins.values())

    def resolve(self, agent_uri: str, node_config: dict) -> object | None:
        """Resolve an agent URI to an adapter via entry point plugins.

        Lazy-loads the plugin class on first call and caches the instance.
        Returns None if no plugin matches the URI prefix.
        """
        prefix = agent_uri.split("://")[0] if "://" in agent_uri else None
        if prefix is None or prefix not in self._plugins:
            return None

        # Lazy-load on first call
        if prefix not in self._instances:
            ep = self._entry_points[prefix]
            try:
                cls = ep.load()
                self._instances[prefix] = cls()
            except Exception as exc:
                meta = self._plugins[prefix]
                raise RuntimeError(
                    f"Plugin '{meta.name}' failed to load: {exc}. "
                    f"Try: pip install {meta.package_name or meta.name}"
                ) from exc

        instance = self._instances[prefix]
        uri_part = agent_uri.split("://", 1)[1] if "://" in agent_uri else agent_uri
        return instance.create_adapter(uri_part, node_config)

    def resolve_inline(
        self, adapter_class: str, uri: str, config: dict,
    ) -> object:
        """Load an adapter class from a dotted import path.

        The class must have a callable create_adapter() method.
        """
        try:
            module_path, class_name = adapter_class.rsplit(".", 1)
        except ValueError:
            raise ValueError(
                f"Cannot import adapter_class '{adapter_class}': "
                f"expected dotted path like 'package.module.ClassName'"
            ) from None

        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ValueError(
                f"Cannot import adapter_class '{adapter_class}': {exc}"
            ) from exc

        cls = getattr(module, class_name, None)
        if cls is None:
            raise ValueError(
                f"Cannot import adapter_class '{adapter_class}': "
                f"module '{module_path}' has no attribute '{class_name}'"
            )

        if not hasattr(cls, "create_adapter") or not callable(getattr(cls, "create_adapter")):
            raise ValueError(
                f"Class '{adapter_class}' is not a valid Binex plugin: "
                f"missing create_adapter() method"
            )

        instance = cls()
        uri_part = uri.split("://", 1)[1] if "://" in uri else uri
        return instance.create_adapter(uri_part, config)

    def all_plugins(self) -> list[dict]:
        """Return metadata for all discovered plugins without loading classes."""
        return [
            {
                "prefix": meta.prefix,
                "name": meta.name,
                "package_name": meta.package_name,
                "version": meta.version,
            }
            for meta in self._plugins.values()
        ]
