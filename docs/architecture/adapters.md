# Adapters

## Overview

Adapters bridge the Dispatcher to concrete agent implementations. The
`AgentAdapter` protocol defines the contract; several implementations ship with
Binex. Adapter selection is driven by URI prefixes in workflow YAML:
`llm://` for LLM calls via litellm, `a2a://` for remote A2A agents,
`local://` for in-process Python handlers, `human://` for interactive
human-in-the-loop steps, and `langchain://`, `crewai://`, `autogen://` for
third-party framework integration. Custom adapters can be added via the
plugin system.

## Components

| Adapter             | Module             | Prefix     | Backend             |
|---------------------|--------------------|------------|---------------------|
| LLMAdapter          | `adapters/llm.py`  | `llm://`   | litellm.acompletion |
| A2AAgentAdapter     | `adapters/a2a.py`  | `a2a://`   | HTTP POST /execute  |
| LocalPythonAdapter  | `adapters/local.py`| `local://`  | async Python callable|
| HumanInputAdapter   | `adapters/human.py`| `human://input` | Terminal text prompt |
| HumanApprovalAdapter| `adapters/human.py`| `human://approve`| Terminal y/n approval |
| A2AExternalGatewayAdapter | `adapters/a2a.py` | `a2a://` + `--gateway` | HTTP POST /route (via Gateway) |
| LangChainAdapter  | `adapters/langchain_adapter.py` | `langchain://` | LangChain Runnable `.invoke()` |
| CrewAIAdapter     | `adapters/crewai_adapter.py` | `crewai://` | CrewAI Crew `.kickoff()` |
| AutoGenAdapter    | `adapters/autogen_adapter.py` | `autogen://` | AutoGen Team `.run()` |

## Interfaces

### Protocol

```python
class AgentAdapter(Protocol):
    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> list[Artifact]: ...

    async def cancel(self, task_id: str) -> None: ...
    async def health(self) -> AgentHealth: ...
```

### LLMAdapter

Forwards optional kwargs to `litellm.acompletion()` only when not `None`.
Per-node config (`temperature`, `api_base`, `api_key`, `max_tokens`) comes
from `NodeSpec.config`.

```python
class LLMAdapter:
    def __init__(
        self,
        model: str,
        prompt_template: str | None = None,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None: ...

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> list[Artifact]: ...
```

### A2AAgentAdapter

Communicates with remote agents over the A2A protocol. The remote agent must
expose `POST /execute` and `GET /health`. When an optional `gateway` parameter
is provided, requests are routed through the Gateway instead of directly to the
agent endpoint.

```python
class A2AAgentAdapter:
    def __init__(self, endpoint: str, *, gateway: "Gateway | None" = None) -> None: ...

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> list[Artifact]: ...

    async def cancel(self, task_id: str) -> None: ...
    async def health(self) -> AgentHealth: ...
```

### LocalPythonAdapter

Wraps an async Python callable. The handler receives the task and input
artifacts and returns output artifacts.

```python
HandlerType = Callable[
    [TaskNode, list[Artifact]],
    Coroutine[Any, Any, list[Artifact]],
]

class LocalPythonAdapter:
    def __init__(self, handler: HandlerType) -> None: ...

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> list[Artifact]: ...
```

### HumanInputAdapter

Prompts the user for free-text input via `click.prompt`. The node's
`system_prompt` is used as the prompt message. Returns a single artifact
with type `"human_input"`.

### HumanApprovalAdapter

Displays input artifacts and prompts the user with an approve/reject choice
(`y`/`n`). Returns a single artifact with type `"decision"` and content
`"approved"` or `"rejected"`. Commonly paired with the `when` field on
downstream nodes to implement conditional branching.

## Data Flow

```
Workflow YAML
    |
    v
NodeSpec.agent = "llm://gpt-4o"      (or "a2a://...", "local://...")
    |
    v
Dispatcher.dispatch(task, artifacts, trace_id)
    |
    +--- lookup agent_key in registry
    |
    v
+-------------------+    +---------------------+    +---------------------+
|   LLMAdapter      |    |  A2AAgentAdapter     |    | LocalPythonAdapter  |
|                    |    |                      |    |                     |
| litellm           |    | POST /execute        |    | handler(task, arts) |
| .acompletion()    |    |  {task_id, skill,    |    |                     |
|                    |    |   trace_id,          |    |                     |
| model, prompt,    |    |   artifacts}         |    |                     |
| temperature, ...  |    |                      |    |                     |
+--------+----------+    +----------+-----------+    +----------+----------+
         |                          |                           |
         v                          v                           v
    list[Artifact]            list[Artifact]              list[Artifact]
         |                          |                           |
         +----------+---------------+---------------------------+
                    |
                    v
          returned to Dispatcher --> Orchestrator --> stores
```

## Gateway Integration

When a `gateway.yaml` file is detected in the project directory, `A2AAgentAdapter` routes requests through an embedded Gateway running in-process. This provides capability-based routing, automatic failover, and health checking without requiring a separate service.

When the `--gateway URL` flag is passed to `binex run`, `A2AExternalGatewayAdapter` is used instead. It routes requests through a standalone Gateway service via `POST /route`, delegating agent selection and failover to the external process.

The Gateway provides:

- **Capability-based routing** — select agents based on declared skills and routing strategy
- **Retry and failover** — automatic retries with configurable failover to alternative agents
- **API key authentication** — forward per-agent credentials from Gateway configuration
- **Health checking** — periodic health probes with automatic agent deregistration on failure

See [binex gateway](../cli/gateway.md) for Gateway CLI and configuration details.

## Framework Adapters

Binex includes thin-wrapper adapters for popular AI frameworks. These are installed as optional extras and registered through the plugin system.

### Installation

```bash
pip install binex[langchain]   # LangChain support
pip install binex[crewai]      # CrewAI support
pip install binex[autogen]     # AutoGen support
```

### How They Work

Each framework adapter imports a user-provided Python object by dotted path and calls its framework-specific method:

| Framework | Prefix | Async Method | Sync Fallback | Expected Object |
|-----------|--------|-------------|---------------|-----------------|
| LangChain | `langchain://` | `.ainvoke()` | `.invoke()` | Runnable |
| CrewAI | `crewai://` | `.kickoff_async()` | `.kickoff()` | Crew |
| AutoGen | `autogen://` | `.a_run()` | `.run()` | Team / AgentChat |

The URI after `://` is the dotted import path to the Python object:

```yaml
nodes:
  summarize:
    agent: "langchain://myproject.chains.summarizer"
```

**Data mapping**: single input artifact's `content` is passed directly; multiple artifacts are merged into a `{"artifact_id": content}` dict. Output is wrapped into an artifact (dicts are JSON-serialized).

**Sync/async**: if the object has the async method, it's called directly. Otherwise, the sync method is run in a thread via `asyncio.to_thread()`.

## Plugin System

Binex supports custom adapters via a plugin system based on Python entry points.

### Plugin Contract

A plugin is a class with a `prefix` attribute and a `create_adapter()` factory method:

```python
class MyPlugin:
    prefix = "custom"  # → custom:// in workflow YAML

    def create_adapter(self, uri: str, node_config: dict):
        return MyAdapter(uri=uri, **node_config)
```

### Registration

**Via entry points** (for pip packages):

```toml
[project.entry-points."binex.plugins"]
custom = "my_package:MyPlugin"
```

**Via inline `adapter_class`** (for one-off adapters):

```yaml
nodes:
  step_a:
    agent: "custom://my-handler"
    config:
      adapter_class: "myproject.adapters.CustomPlugin"
```

### Resolution Order

When the dispatcher encounters an unknown agent prefix:

1. Built-in adapters (`local://`, `llm://`, `human://`, `a2a://`)
2. Inline `adapter_class` from node config
3. Entry point plugins
4. Error with actionable message

### CLI Commands

- `binex plugins list [--json]` — show installed plugins
- `binex plugins check <workflow.yaml>` — verify all adapters are available (exit code 1 if missing)

See [binex plugins](../cli/plugins.md) for details.
