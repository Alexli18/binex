# Budget & Cost Tracking Guide

Practical guide to controlling and monitoring LLM spend in Binex workflows.

## Quick Start

### 1. Add budget to your workflow

```yaml
name: my-pipeline
budget:
  max_cost: 5.00
  policy: stop        # "stop" or "warn"

nodes:
  summarize:
    agent: llm://openai/gpt-4o
    inputs: { text: "${user.text}" }
    outputs: [summary]
  translate:
    agent: llm://anthropic/claude-sonnet-4-20250514
    inputs: { text: "${node.summarize.summary}" }
    outputs: [translation]
    depends_on: [summarize]
```

### 2. Run the workflow

```bash
binex run workflow.yaml --var text="Hello world"
```

### 3. Inspect costs

```bash
binex cost show <run_id>
binex cost history <run_id>
```

## Budget Policies

| Policy | Behavior | Use case |
|--------|----------|----------|
| `stop` | Skips remaining nodes, sets status `"over_budget"` | Hard spending limits, production |
| `warn` | Logs warning to stderr, continues execution | Development, monitoring |

### `policy: stop` — hard limit

```yaml
budget:
  max_cost: 1.00
  policy: stop
```

Output when budget exceeded:

```
Run: run_abc123 — over_budget
Cost: $1.12
Budget: $1.00 (remaining: $-0.12)
Budget exceeded — run stopped
Spent: $1.12 / Budget: $1.00
```

Skipped nodes appear in `RunSummary.skipped_nodes`. The orchestrator checks budget **between scheduling batches** — a running node is not interrupted mid-execution.

### `policy: warn` — soft limit

```yaml
budget:
  max_cost: 10.00
  policy: warn
```

All nodes execute. A warning is logged to stderr when cost exceeds `max_cost`.

## Per-Node Budget

Individual nodes can have their own `max_cost` limit. Policy is inherited from the workflow level (default: `stop`).

### Shorthand syntax

```yaml
nodes:
  cheap_node:
    agent: llm://gpt-4o-mini
    outputs: [draft]
    budget: 0.50        # equivalent to budget: { max_cost: 0.50 }
```

### Full form

```yaml
nodes:
  expensive_node:
    agent: llm://gpt-4o
    outputs: [result]
    budget:
      max_cost: 3.00
```

### Interaction with workflow budget

When both are set, the effective limit is `min(node_budget, remaining_workflow_budget)`:

```yaml
budget:
  max_cost: 5.00      # workflow total
  policy: stop

nodes:
  a:
    budget: 3.00       # effective: min(3.00, 5.00) = 3.00
  b:
    budget: 4.00       # if a cost $2.50: effective = min(4.00, 2.50) = 2.50
    depends_on: [a]
```

### Per-node budget works without workflow budget

```yaml
# No workflow budget — per-node limits still enforced (default policy: stop)
nodes:
  expensive:
    agent: llm://gpt-4o
    outputs: [result]
    budget: 2.00
```

### Cost show with per-node budget

```bash
$ binex cost show run_abc123

Node breakdown:
cheap_node           $0.30  (budget: $0.50, remaining: $0.20)
expensive_node       $2.80  (budget: $3.00, remaining: $0.20)
unbounded_node       $1.10
```

### Retry behavior

When a node with budget fails and has `max_retries > 1`:
- **Before retry:** orchestrator checks remaining node budget
- **`policy: stop`** → retry skipped, node marked failed
- **`policy: warn`** → user prompted: "Continue? [y/N]"

## Cost Inspection Commands

### `binex cost show <run_id>` — summary

```bash
$ binex cost show run_f7a1b2c3

Run: run_f7a1b2c3

Total cost: $3.47
Budget: $5.00
Remaining: $1.53

Node breakdown:
summarize            $1.23
translate            $2.24
```

JSON output (for scripts/CI):

```bash
$ binex cost show run_f7a1b2c3 --json
```

```json
{
  "run_id": "run_f7a1b2c3",
  "total_cost": 3.47,
  "currency": "USD",
  "budget": 5.0,
  "remaining_budget": 1.53,
  "nodes": [
    {
      "task_id": "summarize",
      "cost": 1.23,
      "source": "llm_tokens",
      "prompt_tokens": 512,
      "completion_tokens": 256,
      "model": "gpt-4o"
    },
    {
      "task_id": "translate",
      "cost": 2.24,
      "source": "llm_tokens",
      "prompt_tokens": 1024,
      "completion_tokens": 430,
      "model": "claude-sonnet-4-20250514"
    }
  ]
}
```

`budget` and `remaining_budget` fields appear only when the workflow defines a `budget` section.

### `binex cost history <run_id>` — chronological events

```bash
$ binex cost history run_f7a1b2c3

Cost history for run_f7a1b2c3:

2026-03-11 14:22:01  summarize            $1.23  (llm_tokens)
2026-03-11 14:22:05  translate            $2.24  (llm_tokens)
```

JSON output:

```bash
$ binex cost history run_f7a1b2c3 --json
```

```json
{
  "run_id": "run_f7a1b2c3",
  "records": [
    {
      "id": "cost_a1b2c3",
      "task_id": "summarize",
      "cost": 1.23,
      "currency": "USD",
      "source": "llm_tokens",
      "timestamp": "2026-03-11T14:22:01.123456+00:00"
    },
    {
      "id": "cost_d4e5f6",
      "task_id": "translate",
      "cost": 2.24,
      "currency": "USD",
      "source": "llm_tokens",
      "timestamp": "2026-03-11T14:22:05.456789+00:00"
    }
  ]
}
```

## Cost Sources

| Source | Adapter | Description |
|--------|---------|-------------|
| `llm_tokens` | LLM | Calculated via `litellm.completion_cost()` |
| `llm_tokens_unavailable` | LLM | Model not in pricing table; tokens recorded, cost $0 |
| `agent_report` | A2A | Cost reported by the remote agent |
| `local` | Local, Human | Always $0 |
| `unknown` | A2A | Remote agent did not report cost |

## Common Patterns

### No budget — cost tracking only

```yaml
name: unbudgeted
nodes:
  worker:
    agent: llm://openai/gpt-4o
    outputs: [result]
```

```bash
binex run workflow.yaml
binex cost show <run_id>    # costs still recorded
```

### CI/CD — fail on overspend

```bash
REMAINING=$(binex cost show "$RUN_ID" --json | jq '.remaining_budget')
if (( $(echo "$REMAINING < 0" | bc -l) )); then
  echo "Budget exceeded!" && exit 1
fi
```

### Cost estimates for planning

```yaml
nodes:
  expensive:
    agent: llm://openai/gpt-4o
    outputs: [result]
    cost:
      estimate: 2.50    # informational only, does not affect execution
```

## Data Storage

Cost records live in `.binex/binex.db` in the `cost_records` table. Each record links to a `run_id` and `task_id` (node).

## See Also

- [`binex cost`](cost.md) — CLI reference
- [Workflow Format — Budget](../workflows/format.md#budget-budgetconfig) — YAML schema
- [`binex run`](run.md) — running workflows
