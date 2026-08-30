"""The set of built-in agent URI prefixes must have exactly one definition.

It used to be spelled out in three places — ``PluginRegistry._builtin_prefixes``,
the ``if/elif`` chain in ``cli.adapter_registry``, and the "available prefixes"
error message. They drifted: ``cao`` was added to the dispatch chain but never
reserved, so a plugin could claim ``cao://``, pass conflict validation, and then
be silently shadowed by the built-in branch. These tests pin the single source
of truth so the lists cannot diverge again.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from binex.adapters.base import BUILTIN_AGENT_PREFIXES
from binex.plugins import PluginRegistry


def _make_entry_point(name: str, value: str, *, pkg: str = "binex-rogue"):
    ep = MagicMock()
    ep.name = name
    ep.value = value
    ep.dist = MagicMock()
    ep.dist.name = pkg
    ep.dist.version = "1.0.0"
    return ep


@pytest.mark.parametrize("prefix", sorted(BUILTIN_AGENT_PREFIXES))
def test_plugin_cannot_claim_any_builtin_prefix(prefix: str):
    """Every prefix the dispatch chain handles must be reserved from plugins."""
    ep = _make_entry_point(prefix, "rogue:Rogue")
    registry = PluginRegistry()

    with patch("binex.plugins.entry_points", return_value=[ep]):
        with pytest.raises(ValueError, match=f"cannot use prefix '{prefix}'"):
            registry.discover()


def test_cao_is_a_reserved_builtin_prefix():
    """Regression: cao:// is dispatched to the built-in CAO adapter, not plugins."""
    assert "cao" in BUILTIN_AGENT_PREFIXES


def test_registry_reserves_exactly_the_builtin_prefixes():
    """The registry's reserved set is the shared constant, not a private copy."""
    assert set(PluginRegistry._builtin_prefixes) == set(BUILTIN_AGENT_PREFIXES)


def test_dispatch_chain_covers_every_builtin_prefix():
    """The prefix→registrar table and the constant cannot drift apart."""
    from binex.cli.adapter_registry import _builtin_registrars
    from binex.runtime.dispatcher import Dispatcher

    registrars = _builtin_registrars(
        Dispatcher(),
        workflow_dir=None,
        mcp_manager=None,
        web_mode=False,
        gateway_url=None,
        session_store=None,
        event_callback=None,
    )

    assert set(registrars) == set(BUILTIN_AGENT_PREFIXES)


def test_unknown_agent_error_lists_every_builtin_prefix():
    """The 'available prefixes' hint is derived from the constant."""
    from binex.cli.adapter_registry import _register_plugin_adapter
    from binex.models.workflow import NodeSpec
    from binex.runtime.dispatcher import Dispatcher

    node = NodeSpec(id="n", agent="bogus://thing", outputs=["out"])

    with pytest.raises(ValueError) as excinfo:
        _register_plugin_adapter(Dispatcher(), "bogus://thing", node, None)

    message = str(excinfo.value)
    for prefix in BUILTIN_AGENT_PREFIXES:
        assert f"{prefix}://" in message
