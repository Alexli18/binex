# Workflows

## What is a Workflow?

```yaml
name: simple-pipeline
description: A two-step produce-and-consume pipeline
defaults:
  deadline_ms: 120000
  retry_policy:
    max_retries: 3
    backoff: exponential
nodes:
  producer:
    agent: "local://echo"
    system_prompt: produce
    inputs:
      data: "${user.input}"
    outputs: [result]
  consumer:
    agent: "local://echo"
    system_prompt: consume
    inputs:
      data: "${producer.result}"
    outputs: [final]
    depends_on: [producer]
```

A workflow is a directed acyclic graph (DAG) of nodes defined in YAML. Each node maps to an [agent](agents.md) invocation. The runtime resolves the DAG, executes nodes in dependency order, and threads [artifacts](artifacts.md) between them.

## How It Works

The workflow is parsed into a `WorkflowSpec` model:

```python
class WorkflowSpec(BaseModel):
    name: str
    description: str = ""
    nodes: dict[str, NodeSpec]
    defaults: DefaultsSpec | None = None
```

Each `NodeSpec` declares its agent, inputs, outputs, and dependencies. Two types of variable references exist:

- **`${user.*}`** -- resolved at load time from user-provided parameters.
- **`${node.*}`** -- resolved at runtime by fetching the named artifact from a predecessor node's outputs.

The `defaults` block sets fallback `deadline_ms` and `retry_policy` for all nodes. Individual nodes can override these with their own `deadline_ms`, `retry_policy`, and `config` fields.

Nodes without dependencies run in parallel. The runtime walks the DAG layer by layer, blocking on each layer's completion before starting the next.

## Example

Run a workflow from the CLI:

```bash
binex run examples/simple.yaml --var input="Hello, Binex"
```

## Related Concepts

- [Agents](agents.md) -- each node delegates to an agent
- [Artifacts](artifacts.md) -- inputs and outputs are artifacts
- [Execution](execution.md) -- each node execution is tracked as an execution record
