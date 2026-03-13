# binex run / binex cancel

## Synopsis

```
binex run [OPTIONS] WORKFLOW_FILE
binex cancel RUN_ID
```

## Description

`binex run` executes a workflow definition. It:

1. Loads the YAML file (resolving `${user.*}` variable substitutions)
2. Validates the DAG structure (no cycles, valid dependencies)
3. Auto-registers adapters for all referenced agents (`local://`, `llm://`, `a2a://`, `human://`)
4. Executes nodes in dependency order (parallel where possible)
5. Persists execution records and artifacts to `.binex/`

`binex cancel` marks a running workflow as cancelled.

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Workflow completed successfully |
| `1` | Workflow failed (one or more nodes errored) or cancel failed |
| `2` | Workflow validation failed (invalid YAML, DAG cycle, etc.) |

## Options

### run

| Option | Type | Description |
|---|---|---|
| `WORKFLOW_FILE` | `Path` (must exist) | Workflow YAML file to execute |
| `--var` | `key=value` (repeatable) | Variable substitution for `${user.*}` placeholders. Can be specified multiple times. |
| `--json-output` / `--json` | flag | Output run summary as JSON |
| `--verbose` / `-v` | flag | Show step-by-step progress with `[N/total]` counters, input dependency arrows, artifact contents after each step, and skipped node indicators |
| `--stream / --no-stream` | flag | Stream LLM output tokens in real-time. Auto-detected: enabled for TTY terminals, disabled when piping to a file |

### cancel

| Option | Type | Description |
|---|---|---|
| `RUN_ID` | `string` | ID of the run to cancel |

## Successful Run

```bash
$ binex run workflows/content-pipeline.yaml --var topic="AI safety"

Run ID: run_f7a1b2c3-4d5e-6f7a-8b9c-0d1e2f3a4b5c
Workflow: content-pipeline
Status: completed
Nodes: 4/4 completed
╭──────────── format_output ────────────╮
│                                       │
│ # AI Safety Report                    │
│                                       │
│ ## Key Findings                       │
│ ...                                   │
│                                       │
╰───────────────── result ──────────────╯
```

When `rich` is installed, terminal nodes display their output in a styled panel. Without `rich`, output is printed as plain text.

## Failed Run

```bash
$ binex run workflows/content-pipeline.yaml --var topic="AI safety"

  [summarize] Error: litellm.APIError: Rate limit exceeded
Run ID: run_d8e9f0a1-2b3c-4d5e-6f7a-8b9c0d1e2f3a
Workflow: content-pipeline
Status: failed
Nodes: 2/4 completed
Failed: 1

Tip: run 'binex debug run_d8e9f0a1-2b3c-4d5e-6f7a-8b9c0d1e2f3a' for full details
```

Node errors are printed to stderr. When a run fails, a tip pointing to `binex debug` is shown automatically.

## Verbose Output (`-v`)

Verbose mode shows real-time progress as each node executes:

```bash
$ binex run workflows/content-pipeline.yaml --var topic="AI safety" -v

  [1/4] fetch_data ...
  [fetch_data] -> result:
{"articles": ["article1.txt", "article2.txt"]}

  [2/4] transform ...
        <- fetch_data
  [transform] -> result:
{"cleaned": "Merged text from 2 articles..."}

  [3/4] summarize ...
        <- transform
  [summarize] -> result:
AI safety is a rapidly growing field focusing on...

  [4/4] format_output ...
        <- summarize
  [format_output] -> result:
# AI Safety Report
## Key Findings
...

Run ID: run_f7a1b2c3-4d5e-6f7a-8b9c-0d1e2f3a4b5c
Workflow: content-pipeline
Status: completed
Nodes: 4/4 completed
```

The `<- node_name` arrows show input dependencies for each step.

### Skipped Nodes

Nodes with a `when` condition that evaluates to false are skipped. In verbose mode, they are shown:

```
  [skipped] optional_review
```

Skipped nodes count toward `total_nodes` but not `completed_nodes` or `failed_nodes`.

## JSON Output

```bash
$ binex run workflows/content-pipeline.yaml --var topic="AI safety" --json
```

```json
{
  "run_id": "run_f7a1b2c3-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
  "workflow_name": "content-pipeline",
  "status": "completed",
  "total_nodes": 4,
  "completed_nodes": 4,
  "failed_nodes": 0,
  "started_at": "2026-03-09T14:30:00.123456",
  "finished_at": "2026-03-09T14:30:12.654321",
  "output": {
    "format_output": "# AI Safety Report\n\n## Key Findings\n..."
  }
}
```

The `output` field contains the content of terminal nodes (nodes with no downstream dependents).

With `--json -v`, the output includes all artifacts:

```json
{
  "run_id": "run_f7a1b2c3-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
  "workflow_name": "content-pipeline",
  "status": "completed",
  "total_nodes": 4,
  "completed_nodes": 4,
  "failed_nodes": 0,
  "output": {
    "format_output": "# AI Safety Report\n..."
  },
  "artifacts": [
    {
      "node": "fetch_data",
      "type": "result",
      "content": {"articles": ["article1.txt", "article2.txt"]}
    },
    {
      "node": "transform",
      "type": "result",
      "content": {"cleaned": "Merged text from 2 articles..."}
    },
    {
      "node": "summarize",
      "type": "result",
      "content": "AI safety is a rapidly growing field..."
    },
    {
      "node": "format_output",
      "type": "result",
      "content": "# AI Safety Report\n..."
    }
  ]
}
```

## Budget & Cost Output

When a workflow defines a `budget` section, the run output includes budget information:

```bash
$ binex run workflow.yaml

Run ID: run_f7a1b2c3
Workflow: research-pipeline
Status: completed
Nodes: 3/3 completed
Cost: $2.50
Budget: $5.00 (remaining: $2.50)
```

With `--json`:

```json
{
  "status": "completed",
  "total_cost": 2.5,
  "budget": 5.0,
  "remaining_budget": 2.5
}
```

When budget is exceeded with policy `"stop"`:

```bash
$ binex run workflow.yaml

Run ID: run_d8e9f0a1
Workflow: research-pipeline
Status: over_budget
Nodes: 2/3 completed
Budget exceeded — run stopped
Spent: $5.23 / Budget: $5.00
```

Use `binex cost show <run-id>` for a detailed per-node cost breakdown.

## Streaming Output (`--stream`)

When streaming is enabled, LLM tokens are printed to the terminal as they arrive:

```bash
$ binex run workflow.yaml --stream

  [1/2] planner ...
  Planning the research approach for quantum computing...▌

  [2/2] summarizer ...
  Quantum computing represents a fundamental shift in...▌
```

Streaming is auto-detected: it is enabled when the output is a TTY (interactive terminal) and disabled when piping to a file or another command. Use `--stream` or `--no-stream` to override.

Streaming works with all LLM providers supported by LiteLLM. Non-LLM adapters (`local://`, `a2a://`, `human://`) are not affected.

## Validation Errors

If the workflow YAML has structural problems, `binex run` exits with code `2` before executing anything:

```bash
$ binex run workflows/broken.yaml
Error: Node 'summarize' depends on unknown node 'nonexistent'
Error: Cycle detected: transform -> summarize -> transform
```

## Variable Substitution

Use `--var` to pass values into `${user.*}` placeholders in the workflow YAML:

```yaml
# workflow.yaml
name: report-pipeline
nodes:
  fetch:
    agent: local://fetch
    skill: "Fetch articles about ${user.topic}"
  summarize:
    agent: llm://openai/gpt-4o
    skill: "Summarize in ${user.language}"
    depends_on: [fetch]
```

```bash
binex run workflow.yaml --var topic="quantum computing" --var language="Spanish"
```

Variables are resolved at load time. If a `${user.*}` placeholder has no matching `--var`, it is left as-is in the string.

### Invalid `--var` Format

```
$ binex run workflow.yaml --var "topic quantum computing"
Error: Invalid var format: topic quantum computing (expected key=value)
```

## Environment Variables

Binex loads `.env` from the current directory at startup (via `python-dotenv`). This is the standard way to configure API keys:

```bash
# .env
OPENAI_API_KEY=sk-proj-abc123...
ANTHROPIC_API_KEY=sk-ant-abc123...
```

Per-node configuration (api_base, api_key, temperature, max_tokens) can also be set in the workflow YAML `config` block:

```yaml
nodes:
  summarize:
    agent: llm://openai/gpt-4o
    skill: "Summarize the document"
    config:
      temperature: 0.3
      max_tokens: 2000
```

## Cancel a Running Workflow

```bash
$ binex cancel run_f7a1b2c3-4d5e-6f7a-8b9c-0d1e2f3a4b5c
Run 'run_f7a1b2c3-4d5e-6f7a-8b9c-0d1e2f3a4b5c' cancelled.
```

**Error cases:**

```
$ binex cancel run_nonexistent
Error: Run 'run_nonexistent' not found.

$ binex cancel run_already_done
Error: Cannot cancel run 'run_already_done' — not running.
```

## Agent Registration

`binex run` auto-registers adapters based on the agent URI prefix in each node:

| Prefix | Adapter | Notes |
|---|---|---|
| `local://` | `LocalPythonAdapter` | Default echo handler (passes input through) |
| `llm://` | `LLMAdapter` | Model name extracted from URI; config forwarded to `litellm.acompletion()` |
| `a2a://` | `A2AAgentAdapter` | Endpoint URL extracted from URI; POSTs to `/execute` |
| `human://input` | `HumanInputAdapter` | Prompts user for text input via terminal |
| `human://approve` | `HumanApprovalAdapter` | Prompts user for approval; returns `"approved"` or `"rejected"` |

## Data Storage

All run data is persisted in the `.binex/` directory (gitignored by default):

- `.binex/binex.db` -- SQLite database with execution records (run metadata, node statuses, latency, errors)
- `.binex/artifacts/` -- JSON files with artifact content and lineage

## Tips

- Use `--json` in scripts and CI pipelines. The `output` field always contains terminal node content.
- Use `-v` during development to watch the pipeline execute step by step.
- Long artifact content (over 4000 characters) is truncated in the terminal panel display. Use `binex artifacts show <id>` to see full content.
- Combine `--json` and `-v` to get both progress logging (on stderr) and structured output (on stdout).
- If a run fails, the tip message points to `binex debug` -- follow it for full error details and node-level inspection.
- The `output` field in JSON mode only includes terminal nodes. Use `-v` to include all intermediate artifacts.

## See Also

- [binex validate](validate.md) -- check workflow before running
- [binex debug](debug.md) -- post-mortem inspection of a run
- [binex diagnose](diagnose.md) -- automated root-cause analysis
- [binex trace](trace.md) -- inspect execution after a run
- [binex replay](replay.md) -- re-run from a specific step
- [binex cost](cost.md) -- inspect cost data for a run
- [binex artifacts](artifacts.md) -- inspect individual artifacts
