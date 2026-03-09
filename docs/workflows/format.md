# Workflow YAML Format

Complete schema reference for Binex workflow files.

## Root — `WorkflowSpec`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | yes | Workflow name |
| `description` | `str` | no | Workflow description (default: `""`) |
| `nodes` | `dict[str, NodeSpec]` | yes | Map of node\_id to node definition |
| `defaults` | `DefaultsSpec` | no | Default settings applied to all nodes |

## Node — `NodeSpec`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | no | Auto-set from the dict key |
| `agent` | `str` | yes | Agent URI — one of `local://`, `llm://`, `a2a://` |
| `system_prompt` | `str` | no | System prompt sent to the agent |
| `inputs` | `dict[str, Any]` | no | Input key-value pairs; supports variable interpolation |
| `outputs` | `list[str]` | yes | Artifact names this node produces |
| `depends_on` | `list[str]` | no | Node IDs that must complete before this node runs |
| `config` | `dict[str, Any]` | no | Per-node config forwarded to the adapter (see below) |
| `retry_policy` | `RetryPolicy` | no | Override the default retry settings |
| `deadline_ms` | `int` | no | Override the default deadline for this node |
| `when` | `str` | no | Conditional execution expression (see below) |

### `config` keys (LLM adapter)

| Key | Example | Effect |
|-----|---------|--------|
| `api_base` | `"http://localhost:11434"` | LiteLLM API base URL |
| `api_key` | `"sk-..."` | Provider API key |
| `temperature` | `0.7` | Sampling temperature |
| `max_tokens` | `4096` | Max tokens in completion |

All `config` values are forwarded to `litellm.acompletion()` when not `None`.

### Conditional Execution — `when`

The `when` field enables conditional node execution based on upstream artifact values.
A node with a `when` condition is **skipped** (not failed) if the condition evaluates to false.
Skipped nodes count as resolved for downstream dependency purposes.

**Operators:**

| Operator | Example | Meaning |
|----------|---------|---------|
| `==` | `${review.decision} == approved` | Run only if artifact content equals `"approved"` |
| `!=` | `${review.decision} != rejected` | Run only if artifact content does not equal `"rejected"` |

**Example — approval gate with branching:**

```yaml
publish:
  agent: "local://echo"
  inputs:
    final: "${revise.content}"
  outputs: [result]
  depends_on: [human_review]
  when: "${human_review.decision} == approved"

discard:
  agent: "local://echo"
  inputs: {}
  outputs: [notice]
  depends_on: [human_review]
  when: "${human_review.decision} == rejected"
```

The `when` field is commonly used with `human://approve` nodes but works with any artifact value.

## Defaults — `DefaultsSpec`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `deadline_ms` | `int` | `120000` | Default deadline in milliseconds |
| `retry_policy` | `RetryPolicy` | see below | Default retry policy for all nodes |

## Retry — `RetryPolicy`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_retries` | `int` | `1` | Maximum retry attempts |
| `backoff` | `"fixed"` or `"exponential"` | `"exponential"` | Backoff strategy between retries |

## Variable Interpolation

Two variable scopes are available inside `inputs` values:

| Syntax | Resolved | Description |
|--------|----------|-------------|
| `${user.*}` | Load time | Substituted from `--var` CLI arguments |
| `${node.*}` | Runtime | References an artifact produced by another node |

**Example:**

```yaml
inputs:
  query: "${user.query}"          # --var query="LLM agents"
  plan: "${planner.execution_plan}" # artifact from the planner node
```

## Minimal Valid Workflow

```yaml
name: minimal
nodes:
  only_node:
    agent: "local://echo"
    system_prompt: ping
    inputs:
      msg: "hello"
    outputs: [response]
```

No `defaults`, `description`, `depends_on`, or `config` required.
