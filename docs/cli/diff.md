# binex diff

## Synopsis

```
binex diff RUN_A RUN_B [OPTIONS]
```

## Description

Compare two runs side-by-side. For each node in the workflow, `binex diff` reports:

- **Status changes** -- did a node go from `failed` to `completed` (or vice versa)?
- **Latency delta** -- how much faster or slower was each node?
- **Agent changes** -- was a different agent used (e.g., after a `--agent` swap in replay)?
- **Artifact changes** -- did the output content differ between the two runs?
- **Error resolution** -- was an error introduced or resolved?

The comparison is keyed by `task_id`, so nodes that exist in only one run are shown with `-` for the missing side.

Exits `0` on success. Exits `1` if either run ID is not found.

## Options

| Option | Type | Description |
|---|---|---|
| `RUN_A` | `string` | First run ID (the "baseline") |
| `RUN_B` | `string` | Second run ID (the "comparison") |
| `--json-output` / `--json` | flag | Output as a structured JSON object |
| `--rich` / `--no-rich` | flag | Enable or disable rich table output. Auto-detected by default (enabled if `rich` is installed) |

## Plain Text Output

When `rich` is not installed (or `--no-rich` is passed), the output is a compact text diff:

```
$ binex diff run_a1b2c3d4 run_e5f6a7b8

Comparing: run_a1b2c3d4 vs run_e5f6a7b8
Workflow: content-pipeline
Status: failed vs completed

  fetch_data: (no changes)
  transform:
    status: failed -> completed
    latency: 2340ms -> 1870ms (-470ms)
    artifacts: CHANGED
  summarize:
    status: failed -> completed
    agent: llm://openai/gpt-4o -> llm://anthropic/claude-sonnet-4-20250514
    latency: 4520ms -> 3100ms (-1420ms)
    artifacts: CHANGED
  format_output: (no changes)
```

Each node is listed with its changes. Nodes with no differences show `(no changes)`.

The latency delta is shown in parentheses with a `+` or `-` sign indicating whether the node became slower or faster.

## Rich Output

When `rich` is installed (default), or with `--rich`, the output is a formatted table with color coding:

- **Green** status = `completed`
- **Red** status = `failed`
- **Yellow** row highlight = status changed between runs
- **Green latency delta** = node got faster
- **Red latency delta** = node got slower

```
$ binex diff run_a1b2c3d4 run_e5f6a7b8

╭──────────────────── Run Diff ─────────────────────╮
│ Workflow: content-pipeline                         │
│ Run A: run_a1b2c3d4 failed                        │
│ Run B: run_e5f6a7b8 completed                     │
╰───────────────────────────────────────────────────╯
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Node           ┃ Status A  ┃ Status B  ┃ Latency A┃ Latency B      ┃ Changes                        ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ fetch_data     │ completed │ completed │   450ms  │ 430ms (-20ms)  │ no changes                     │
│ transform      │ failed    │ completed │  2340ms  │ 1870ms (-470ms)│ error resolved                 │
│ summarize      │ failed    │ completed │  4520ms  │ 3100ms (-1420ms)│ agent: llm://openai/gpt-4o -> │
│                │           │           │          │                │ llm://anthropic/claude-sonnet  │
│                │           │           │          │                │ | artifacts changed            │
│ format_output  │ completed │ completed │   120ms  │ 115ms (-5ms)   │ no changes                     │
└────────────────┴───────────┴───────────┴──────────┴────────────────┴────────────────────────────────┘
```

To force plain text output even when `rich` is installed:

```bash
binex diff run_a1b2c3d4 run_e5f6a7b8 --no-rich
```

## JSON Output

The `--json` flag outputs the full structured diff, suitable for programmatic consumption or piping into `jq`:

```bash
$ binex diff run_a1b2c3d4 run_e5f6a7b8 --json
```

```json
{
  "run_a": "run_a1b2c3d4",
  "run_b": "run_e5f6a7b8",
  "workflow_a": "content-pipeline",
  "workflow_b": "content-pipeline",
  "status_a": "failed",
  "status_b": "completed",
  "steps": [
    {
      "task_id": "fetch_data",
      "status_a": "completed",
      "status_b": "completed",
      "status_changed": false,
      "latency_a": 450,
      "latency_b": 430,
      "agent_a": "local://fetch",
      "agent_b": "local://fetch",
      "agent_changed": false,
      "artifacts_changed": false,
      "error_a": null,
      "error_b": null
    },
    {
      "task_id": "transform",
      "status_a": "failed",
      "status_b": "completed",
      "status_changed": true,
      "latency_a": 2340,
      "latency_b": 1870,
      "agent_a": "llm://openai/gpt-4o",
      "agent_b": "llm://openai/gpt-4o",
      "agent_changed": false,
      "artifacts_changed": true,
      "error_a": "context window exceeded",
      "error_b": null
    },
    {
      "task_id": "summarize",
      "status_a": "failed",
      "status_b": "completed",
      "status_changed": true,
      "latency_a": 4520,
      "latency_b": 3100,
      "agent_a": "llm://openai/gpt-4o",
      "agent_b": "llm://anthropic/claude-sonnet-4-20250514",
      "agent_changed": true,
      "artifacts_changed": true,
      "error_a": "upstream dependency failed",
      "error_b": null
    },
    {
      "task_id": "format_output",
      "status_a": "completed",
      "status_b": "completed",
      "status_changed": false,
      "latency_a": 120,
      "latency_b": 115,
      "agent_a": "local://formatter",
      "agent_b": "local://formatter",
      "agent_changed": false,
      "artifacts_changed": false,
      "error_a": null,
      "error_b": null
    }
  ]
}
```

You can extract specific fields with `jq`:

```bash
# Show only nodes where status changed
binex diff run_a1b2c3d4 run_e5f6a7b8 --json | jq '.steps[] | select(.status_changed)'

# Show only nodes where artifacts differ
binex diff run_a1b2c3d4 run_e5f6a7b8 --json | jq '.steps[] | select(.artifacts_changed) | .task_id'
```

## Error Handling

If either run ID does not exist in the store, the command exits with code `1`:

```
$ binex diff run_nonexistent run_e5f6a7b8
Error: Run 'run_nonexistent' not found
```

## Use Cases

### Comparing a Failed Run vs Successful Re-Run

After a run fails, you might fix the issue (update an API key, adjust a prompt, increase `max_tokens`) and re-run the same workflow. Use `diff` to confirm which nodes were affected:

```bash
# Original run failed at the summarize step
binex run workflows/report.yaml --var topic="Q4 earnings"
# Run ID: run_f8e7d6c5  Status: failed

# Fix the prompt and re-run
binex run workflows/report.yaml --var topic="Q4 earnings"
# Run ID: run_a9b8c7d6  Status: completed

# Compare to see what changed
binex diff run_f8e7d6c5 run_a9b8c7d6
```

### Comparing Runs with Different LLM Providers

Use `binex replay` with agent swaps, then `diff` to see how a different model performs:

```bash
# Replay with a different model
binex replay run_a1b2c3d4 \
  --from summarize \
  --workflow workflows/report.yaml \
  --agent summarize=llm://anthropic/claude-sonnet-4-20250514

# Replay produced run_x9y8z7w6 — now compare
binex diff run_a1b2c3d4 run_x9y8z7w6
```

The diff will show `agent_changed: true` for the `summarize` node, along with any differences in output content and latency.

### Scripting with JSON Output

Use `--json` in CI pipelines to detect regressions:

```bash
# Fail CI if any node changed status from completed to failed
REGRESSIONS=$(binex diff "$BASELINE_RUN" "$CURRENT_RUN" --json \
  | jq '[.steps[] | select(.status_a == "completed" and .status_b == "failed")] | length')

if [ "$REGRESSIONS" -gt 0 ]; then
  echo "Regression detected: $REGRESSIONS nodes failed"
  exit 1
fi
```

## Tips

- Run A is the "baseline" and Run B is the "comparison". Put the older/reference run first.
- The diff compares artifact **content**, not artifact IDs. Two runs producing identical text from different artifact IDs will show `artifacts_changed: false`.
- Nodes that exist in only one run (e.g., workflow was modified between runs) will show `-` for the missing side's status and latency.
- Combine with `binex debug` to investigate specific nodes flagged by the diff.

## See Also

- [binex replay](replay.md) -- create a forked run to compare
- [binex debug](debug.md) -- post-mortem inspection of a run
- [binex trace](trace.md) -- inspect individual runs
