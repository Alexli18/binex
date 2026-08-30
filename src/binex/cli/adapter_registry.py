"""Shared adapter registration for CLI commands (run, start, replay)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from binex.adapters.base import BUILTIN_AGENT_PREFIXES
from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.dispatcher import Dispatcher

_gateway_cache: dict[str, Any] = {}


async def _default_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
    """Default local handler that echoes input artifacts."""
    content = {a.id: a.content for a in inputs} if inputs else {"msg": "no input"}
    return [
        Artifact(
            id=f"art_{task.node_id}",
            run_id=task.run_id,
            type="result",
            content=content,
            lineage=Lineage(
                produced_by=task.node_id,
                derived_from=[a.id for a in inputs],
            ),
        )
    ]


def _register_local_adapter(
    dispatcher: Dispatcher, agent: str,
) -> None:
    dispatcher.register_adapter(
        agent, LocalPythonAdapter(handler=_default_handler),
    )


def _register_llm_adapter(
    dispatcher: Dispatcher,
    agent: str,
    node: NodeSpec,
    workflow_dir: str | None,
    mcp_manager: Any | None,
) -> None:
    from binex.adapters.llm import LLMAdapter

    model = agent.removeprefix("llm://")
    config = node.config
    dispatcher.register_adapter(
        agent,
        LLMAdapter(
            model=model,
            api_base=config.get("api_base"),
            api_key=config.get("api_key"),
            temperature=config.get("temperature"),
            max_tokens=config.get("max_tokens"),
            workflow_dir=workflow_dir,
            mcp_manager=mcp_manager,
        ),
    )


def _register_human_adapter(
    dispatcher: Dispatcher, agent: str, web_mode: bool,
) -> None:
    if agent == "human://output":
        _register_human_output(dispatcher, agent, web_mode)
    elif agent == "human://input":
        _register_human_input(dispatcher, agent, web_mode)
    else:
        _register_human_approval(dispatcher, agent, web_mode)


def _register_human_output(
    dispatcher: Dispatcher, agent: str, web_mode: bool,
) -> None:
    if web_mode:
        from binex.adapters.web_human import WebHumanOutputAdapter
        from binex.ui.api.events import event_bus
        from binex.ui.api.prompts import pending_prompts

        dispatcher.register_adapter(
            agent, WebHumanOutputAdapter(event_bus, pending_prompts),
        )
    else:
        from binex.adapters.human import HumanOutputAdapter

        dispatcher.register_adapter(agent, HumanOutputAdapter())


def _register_human_input(
    dispatcher: Dispatcher, agent: str, web_mode: bool,
) -> None:
    if web_mode:
        from binex.adapters.web_human import WebHumanInputAdapter
        from binex.ui.api.events import event_bus
        from binex.ui.api.prompts import pending_prompts

        dispatcher.register_adapter(
            agent, WebHumanInputAdapter(event_bus, pending_prompts),
        )
    else:
        from binex.adapters.human import HumanInputAdapter

        dispatcher.register_adapter(agent, HumanInputAdapter())


def _register_human_approval(
    dispatcher: Dispatcher, agent: str, web_mode: bool,
) -> None:
    if web_mode:
        from binex.adapters.web_human import WebHumanApprovalAdapter
        from binex.ui.api.events import event_bus
        from binex.ui.api.prompts import pending_prompts

        dispatcher.register_adapter(
            agent, WebHumanApprovalAdapter(event_bus, pending_prompts),
        )
    else:
        from binex.adapters.human import HumanApprovalAdapter

        dispatcher.register_adapter(agent, HumanApprovalAdapter())


def _register_a2a_adapter(
    dispatcher: Dispatcher,
    agent: str,
    node: NodeSpec,
    gateway_url: str | None,
) -> None:
    endpoint = agent.removeprefix("a2a://")

    routing_hints = None
    if node.routing is not None:
        from binex.gateway.router import RoutingHints

        routing_hints = RoutingHints(**node.routing)

    if gateway_url is not None:
        _register_a2a_external(dispatcher, agent, endpoint, gateway_url, routing_hints)
    else:
        _register_a2a_embedded(dispatcher, agent, endpoint, routing_hints)


def _register_a2a_external(
    dispatcher: Dispatcher,
    agent: str,
    endpoint: str,
    gateway_url: str,
    routing_hints: Any,
) -> None:
    from binex.adapters.a2a import A2AExternalGatewayAdapter

    dispatcher.register_adapter(
        agent,
        A2AExternalGatewayAdapter(
            endpoint=endpoint,
            gateway_url=gateway_url,
            routing_hints=routing_hints,
        ),
    )


def _register_a2a_embedded(
    dispatcher: Dispatcher,
    agent: str,
    endpoint: str,
    routing_hints: Any,
) -> None:
    from binex.adapters.a2a import A2AAgentAdapter

    # Lazy-init gateway (once per register call)
    if "instance" not in _gateway_cache:
        from binex.gateway import create_gateway

        gw = create_gateway(config_path=None)
        # Only use gateway if config was found
        _gateway_cache["instance"] = (
            gw if gw._config is not None else None
        )
    gateway = _gateway_cache["instance"]

    dispatcher.register_adapter(
        agent,
        A2AAgentAdapter(
            endpoint=endpoint,
            gateway=gateway,
            routing_hints=routing_hints,
        ),
    )


def _register_cao_adapter(
    dispatcher: Dispatcher,
    agent: str,
    node: NodeSpec,
    session_store: Any | None,
    event_callback: Any | None = None,
    web_mode: bool = False,
) -> None:
    from binex.adapters.cao import CAOAdapter
    from binex.settings import Settings

    profile = agent.removeprefix("cao://")
    settings = Settings()

    human_input_fn: Any = None
    if web_mode:
        # Web mode: no human_input_fn — adapter emits SSE event
        # and user responds via POST /cao/terminals/{id}/input.
        # The CAO server delivers input to the terminal automatically.
        human_input_fn = None
    else:
        # CLI fallback for human input
        def _cli_human_input(profile_name: str, terminal_id: str) -> str:
            import click
            return str(click.prompt(
                f"CAO agent '{profile_name}' is waiting for input",
            ))
        human_input_fn = _cli_human_input

    dispatcher.register_adapter(
        agent,
        CAOAdapter(
            profile=profile,
            server_url=settings.cao_server_url,
            agent_store_dir=settings.cao_agent_store_dir,
            session_store=session_store,
            cao_config=node.cao,
            event_callback=event_callback,
            human_input_fn=human_input_fn,
        ),
    )


def _builtin_registrars(
    dispatcher: Dispatcher,
    *,
    workflow_dir: str | None,
    mcp_manager: Any | None,
    web_mode: bool,
    gateway_url: str | None,
    session_store: Any | None,
    event_callback: Any | None,
) -> dict[str, Callable[[str, NodeSpec], None]]:
    """Map each built-in URI prefix to the call that registers its adapter.

    Keys must stay in sync with :data:`BUILTIN_AGENT_PREFIXES` — a prefix
    dispatched here but not reserved there could be claimed by a plugin and
    then silently shadowed. ``test_dispatch_chain_covers_every_builtin_prefix``
    pins that.
    """
    return {
        "local": lambda agent, node: _register_local_adapter(dispatcher, agent),
        "llm": lambda agent, node: _register_llm_adapter(
            dispatcher, agent, node, workflow_dir, mcp_manager,
        ),
        "human": lambda agent, node: _register_human_adapter(
            dispatcher, agent, web_mode,
        ),
        "a2a": lambda agent, node: _register_a2a_adapter(
            dispatcher, agent, node, gateway_url,
        ),
        "cao": lambda agent, node: _register_cao_adapter(
            dispatcher, agent, node, session_store, event_callback,
            web_mode=web_mode,
        ),
    }


def _register_plugin_adapter(
    dispatcher: Dispatcher,
    agent: str,
    node: NodeSpec,
    plugin_registry: Any | None,
) -> None:
    adapter = None

    if plugin_registry is not None:
        # Inline adapter_class takes priority (FR-004)
        adapter_class = node.config.get("adapter_class") if node.config else None
        if adapter_class:
            adapter = plugin_registry.resolve_inline(adapter_class, agent, node.config)
        else:
            adapter = plugin_registry.resolve(agent, node.config)

    if adapter is not None:
        dispatcher.register_adapter(agent, adapter)
    else:
        available = [f"{p}://" for p in sorted(BUILTIN_AGENT_PREFIXES)]
        if plugin_registry is not None:
            for p in plugin_registry.all_plugins():
                available.append(f"{p['prefix']}://")
        raise ValueError(
            f"No adapter found for '{agent}'. "
            f"Available prefixes: {', '.join(available)}. "
            f"Install a plugin or use adapter_class in node config."
        )


def register_workflow_adapters(
    dispatcher: Dispatcher,
    spec: WorkflowSpec,
    *,
    agent_swaps: dict[str, str] | None = None,
    workflow_dir: str | None = None,
    gateway_url: str | None = None,
    plugin_registry: Any | None = None,
    web_mode: bool = False,
    mcp_manager: Any | None = None,
    session_store: Any | None = None,
    event_callback: Any | None = None,
) -> None:
    """Register adapters for all agents in a workflow spec.

    Handles local://, llm://, human://, and a2a:// prefixes.
    Skips agents already registered in the dispatcher.

    If *mcp_manager* is None but ``spec.mcp_servers`` is non-empty,
    a new :class:`McpClientManager` is created automatically.
    Returns the *mcp_manager* (may be newly created or the one passed in).
    """
    # Reset gateway cache per call so tests stay isolated
    _gateway_cache.clear()

    # Auto-create MCP manager if workflow declares mcp_servers
    if mcp_manager is None and spec.mcp_servers:
        from binex.tools.mcp_client import McpClientManager

        mcp_manager = McpClientManager(spec.mcp_servers)

    # Store on dispatcher for lifecycle management (orchestrator calls close)
    dispatcher._mcp_manager = mcp_manager  # type: ignore[attr-defined]

    registrars = _builtin_registrars(
        dispatcher,
        workflow_dir=workflow_dir,
        mcp_manager=mcp_manager,
        web_mode=web_mode,
        gateway_url=gateway_url,
        session_store=session_store,
        event_callback=event_callback,
    )

    for node in spec.nodes.values():
        agent = agent_swaps.get(node.id, node.agent) if agent_swaps else node.agent

        if agent in dispatcher._adapters:
            continue

        prefix = agent.split("://")[0] if "://" in agent else None
        register = registrars.get(prefix) if prefix else None
        if register is not None:
            register(agent, node)
        else:
            _register_plugin_adapter(dispatcher, agent, node, plugin_registry)
