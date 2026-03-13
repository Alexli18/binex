"""Shared adapter registration for CLI commands (run, start, replay)."""

from __future__ import annotations

from typing import Any

from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.models.workflow import WorkflowSpec
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


def register_workflow_adapters(
    dispatcher: Dispatcher,
    spec: WorkflowSpec,
    *,
    agent_swaps: dict[str, str] | None = None,
    workflow_dir: str | None = None,
    gateway_url: str | None = None,
    plugin_registry: Any | None = None,
) -> None:
    """Register adapters for all agents in a workflow spec.

    Handles local://, llm://, human://, and a2a:// prefixes.
    Skips agents already registered in the dispatcher.
    """
    # Reset gateway cache per call so tests stay isolated
    _gateway_cache.clear()

    for node in spec.nodes.values():
        if agent_swaps:
            agent = agent_swaps.get(node.id, node.agent)
        else:
            agent = node.agent

        if agent in dispatcher._adapters:
            continue

        if agent.startswith("local://"):
            dispatcher.register_adapter(
                agent, LocalPythonAdapter(handler=_default_handler),
            )
        elif agent.startswith("llm://"):
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
                ),
            )
        elif agent == "human://input":
            from binex.adapters.human import HumanInputAdapter

            dispatcher.register_adapter(agent, HumanInputAdapter())
        elif agent.startswith("human://"):
            from binex.adapters.human import HumanApprovalAdapter

            dispatcher.register_adapter(agent, HumanApprovalAdapter())
        elif agent.startswith("a2a://"):
            endpoint = agent.removeprefix("a2a://")

            # Parse routing hints from NodeSpec if present
            routing_hints = None
            if node.routing is not None:
                from binex.gateway.router import RoutingHints

                routing_hints = RoutingHints(**node.routing)

            if gateway_url is not None:
                # External gateway mode: route through standalone gateway
                from binex.adapters.a2a import A2AExternalGatewayAdapter

                dispatcher.register_adapter(
                    agent,
                    A2AExternalGatewayAdapter(
                        endpoint=endpoint,
                        gateway_url=gateway_url,
                        routing_hints=routing_hints,
                    ),
                )
            else:
                # Embedded gateway mode (original behaviour)
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
        else:
            # Plugin fallback: inline adapter_class, then entry point plugins
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
                available = ["local://", "llm://", "human://", "a2a://"]
                if plugin_registry is not None:
                    for p in plugin_registry.all_plugins():
                        available.append(f"{p['prefix']}://")
                raise ValueError(
                    f"No adapter found for '{agent}'. "
                    f"Available prefixes: {', '.join(available)}. "
                    f"Install a plugin or use adapter_class in node config."
                )
