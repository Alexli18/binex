# binex cost

## Synopsis

```
binex cost show [OPTIONS] RUN_ID
binex cost history [OPTIONS] RUN_ID
```

## Description

`binex cost` inspects cost data recorded during workflow execution. Every adapter reports a cost after each node execution — LLM adapters calculate token-based costs via `litellm.completion_cost()`, while local and human adapters report $0.

Two subcommands are available:

- **`show`** — cost breakdown with total, budget info, and per-node costs
- **`history`** — chronological list of cost events with timestamps

## Options

| Option | Type | Description |
|---|---|---|
| `RUN_ID` | `string` | ID of the run to inspect |
| `--json-output` / `--json` | flag | Output as JSON |

## Cost Sources

Each cost record includes a `source` field indicating how the cost was determined:

| Source | Adapter | Description |
|---|---|---|
| `llm_tokens` | LLM | Calculated from token usage via `litellm.completion_cost()` |
| `llm_tokens_unavailable` | LLM | Model not in LiteLLM pricing table; tokens recorded but cost is $0 |
| `agent_report` | A2A | Cost reported by the remote agent in its response |
| `local` | Local, Human | Always $0 — no external service called |
| `unknown` | A2A | Remote agent did not include cost in response |

## Cost Show

Displays the cost summary for a run:

```bash
$ binex cost show run_f7a1b2c3

Run: run_f7a1b2c3

Total cost: $2.50
Budget: $10.00
Remaining: $7.50

Node breakdown:
planner              $0.50
researcher           $1.20
summarizer           $0.80
```

### JSON Output

```bash
$ binex cost show run_f7a1b2c3 --json
```

```json
{
  "run_id": "run_f7a1b2c3",
  "total_cost": 2.5,
  "currency": "USD",
  "budget": 10.0,
  "remaining_budget": 7.5,
  "nodes": [
    {
      "task_id": "planner",
      "cost": 0.5,
      "source": "llm_tokens",
      "prompt_tokens": 150,
      "completion_tokens": 200,
      "model": "gpt-4o"
    },
    {
      "task_id": "researcher",
      "cost": 1.2,
      "source": "llm_tokens",
      "prompt_tokens": 500,
      "completion_tokens": 800,
      "model": "claude-sonnet-4-20250514"
    },
    {
      "task_id": "summarizer",
      "cost": 0.8,
      "source": "llm_tokens",
      "prompt_tokens": 1000,
      "completion_tokens": 300,
      "model": "gpt-4o"
    }
  ]
}
```

The `budget` and `remaining_budget` fields only appear when the workflow defines a `budget` section.

## Cost History

Displays cost events in chronological order:

```bash
$ binex cost history run_f7a1b2c3

Cost history for run_f7a1b2c3:

2026-03-10 14:30:01  planner              $0.50  (llm_tokens)
2026-03-10 14:30:05  researcher           $1.20  (llm_tokens)
2026-03-10 14:30:08  summarizer           $0.80  (llm_tokens)
```

### JSON Output

```bash
$ binex cost history run_f7a1b2c3 --json
```

```json
{
  "run_id": "run_f7a1b2c3",
  "records": [
    {
      "id": "cost_a1b2c3",
      "task_id": "planner",
      "cost": 0.5,
      "currency": "USD",
      "source": "llm_tokens",
      "timestamp": "2026-03-10T14:30:01.123456+00:00"
    }
  ]
}
```

## Error Cases

```bash
$ binex cost show run_nonexistent
Error: Run 'run_nonexistent' not found.
```

Both `show` and `history` exit with code `1` if the run ID is not found.

## Data Storage

Cost records are stored in the `cost_records` table in `.binex/binex.db` alongside execution records. Each record links to a specific `run_id` and `task_id` (node).

## See Also

- [Budget & Cost Tracking Guide](budget-guide.md) — practical examples and patterns
- [binex run](run.md) — execute a workflow (cost output with `--json`)
- [binex debug](debug.md) — post-mortem inspection
- [Workflow Format — Budget](../workflows/format.md#budget-budgetconfig) — configure budget constraints
