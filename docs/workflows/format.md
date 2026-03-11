# Workflow YAML Format

Complete schema reference for Binex workflow files.

## Root — `WorkflowSpec`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | yes | Workflow name |
| `description` | `str` | no | Workflow description (default: `""`) |
| `nodes` | `dict[str, NodeSpec]` | yes | Map of node\_id to node definition |
| `defaults` | `DefaultsSpec` | no | Default settings applied to all nodes |
| `budget` | `BudgetConfig` | no | Budget constraints for the run (see below) |

## Node — `NodeSpec`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | no | Auto-set from the dict key |
| `agent` | `str` | yes | Agent URI — one of `local://`, `llm://`, `a2a://` |
| `system_prompt` | `str` | no | System prompt sent to the agent (supports `file://` prefix) |
| `inputs` | `dict[str, Any]` | no | Input key-value pairs; supports variable interpolation |
| `outputs` | `list[str]` | yes | Artifact names this node produces |
| `depends_on` | `list[str]` | no | Node IDs that must complete before this node runs |
| `config` | `dict[str, Any]` | no | Per-node config forwarded to the adapter (see below) |
| `retry_policy` | `RetryPolicy` | no | Override the default retry settings |
| `deadline_ms` | `int` | no | Override the default deadline for this node |
| `when` | `str` | no | Conditional execution expression (see below) |
| `cost` | `NodeCostHint` | no | Optional cost estimate for planning (see below) |
| `budget` | `float` or `NodeBudget` | no | Per-node budget limit (shorthand: `budget: 0.50`, full: `budget: { max_cost: 0.50 }`) |

### `config` keys (LLM adapter)

| Key | Example | Effect |
|-----|---------|--------|
| `api_base` | `"http://localhost:11434"` | LiteLLM API base URL |
| `api_key` | `"sk-..."` | Provider API key |
| `temperature` | `0.7` | Sampling temperature |
| `max_tokens` | `4096` | Max tokens in completion |

All `config` values are forwarded to `litellm.acompletion()` when not `None`.

### External System Prompt — `file://`

The `system_prompt` field supports loading content from an external file using the `file://` prefix.
Relative paths are resolved relative to the workflow YAML file's directory. Absolute paths are used as-is.

```yaml
nodes:
  researcher:
    agent: "llm://openai/gpt-4"
    system_prompt: "file://prompts/researcher.md"
    outputs: [findings]
```

If the referenced file does not exist, workflow loading fails with a clear error message.

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

## Budget — `BudgetConfig`

Budget constraints limit the total cost of a workflow run. The orchestrator checks accumulated cost after each batch of nodes.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_cost` | `float` | — | Maximum allowed cost in the specified currency (must be > 0) |
| `currency` | `str` | `"USD"` | Currency code |
| `policy` | `"stop"` or `"warn"` | `"warn"` | What to do when budget is exceeded |

### Budget Policies

| Policy | Behavior |
|--------|----------|
| `stop` | Skip all remaining nodes, set run status to `"over_budget"` |
| `warn` | Log a warning to stderr, continue execution |

**Example:**

```yaml
name: budgeted-pipeline
budget:
  max_cost: 5.0
  policy: stop

nodes:
  planner:
    agent: "llm://gpt-4o"
    outputs: [plan]
  researcher:
    agent: "llm://claude-sonnet-4-20250514"
    outputs: [findings]
    depends_on: [planner]
  summarizer:
    agent: "llm://gpt-4o"
    outputs: [summary]
    depends_on: [researcher]
```

If the accumulated cost exceeds $5.00 after the researcher node, the summarizer is skipped and the run status is `"over_budget"`.

See the [Budget & Cost Tracking Guide](../cli/budget-guide.md) for more examples and patterns.

With `--json`, the run output includes budget information:

```json
{
  "status": "over_budget",
  "total_cost": 5.23,
  "budget": 5.0,
  "remaining_budget": -0.23
}
```

## Node Cost Hint — `NodeCostHint`

Optional cost estimate for planning purposes. Does not affect execution — purely informational.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `estimate` | `float` | `0.0` | Estimated cost for this node (must be >= 0) |

```yaml
nodes:
  expensive_node:
    agent: "llm://gpt-4o"
    outputs: [result]
    cost:
      estimate: 2.50
```

## Per-Node Budget — `NodeBudget`

Individual nodes can have their own budget limits. The policy is inherited from the workflow-level `budget.policy` (default: `stop`).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_cost` | `float` | — | Maximum allowed cost for this node (must be > 0) |

**Shorthand:** `budget: 0.50` is equivalent to `budget: { max_cost: 0.50 }`.

When both workflow and node budgets are defined, the effective limit is `min(node_budget, remaining_workflow_budget)`.

**Pre-check before retry:** If a node has a budget and fails, the orchestrator checks remaining budget before each retry attempt. With `policy: stop`, the retry is skipped if budget is exhausted. With `policy: warn`, the user is prompted via `click.confirm()`.

**Post-check after execution:** After each execution, if the node's accumulated cost exceeds its budget, the policy determines behavior: `stop` discards the result and marks the node failed; `warn` keeps the result and logs a warning.

**Example:**

```yaml
name: per-node-budget
budget:
  max_cost: 10.00
  policy: stop

nodes:
  planner:
    agent: "llm://gpt-4o-mini"
    outputs: [plan]
    budget: 0.50           # shorthand

  researcher:
    agent: "llm://gpt-4o"
    outputs: [findings]
    depends_on: [planner]
    budget:
      max_cost: 3.00       # full form

  summarizer:
    agent: "llm://gpt-4o"
    outputs: [summary]
    depends_on: [researcher]
    budget: 2.00
```

If the planner costs $0.60 (exceeding its $0.50 limit), it is marked as failed and dependent nodes do not run.

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
