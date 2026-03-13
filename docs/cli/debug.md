# binex debug

## Synopsis

```
binex debug <RUN_ID | latest> [OPTIONS]
```

## Description

Post-mortem inspection of a workflow run. Displays a complete debug report including workflow summary, per-node details (agent, prompt, inputs, outputs, errors), skipped nodes with blocking reasons, and timing information.

Use `latest` instead of a run ID to automatically select the most recent run.

## Arguments

| Argument | Required | Description |
|---|---|---|
| `RUN_ID` | Yes | Workflow run identifier, or `latest` for the most recent run |

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--node ID` | `string` | None | Show only the specified node |
| `--errors` | flag | false | Show only failed/timed_out nodes |
| `--json` | flag | false | Output as JSON |
| `--rich` | flag | false | Colored output (requires `rich` library) |

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Run not found / missing dependency |

## Examples

```bash
# Debug the most recent run
binex debug latest

# Full post-mortem report
binex debug abc123

# Focus on a single node
binex debug abc123 --node planner

# Show only errors
binex debug abc123 --errors

# Machine-readable JSON
binex debug abc123 --json

# Colored output (requires: pip install binex[rich])
binex debug abc123 --rich
```

## Output

### Plain text (default)

```
=== Debug: abc123 ===
Workflow: research-pipeline
Status:   failed (2/3 completed)
Duration: 5.0s

-- planner [completed] 100ms ------
  Agent:  llm://gpt-4
  Prompt: Plan the research
  Output: art_planner (result)
          {"plan": "step 1..."}

-- researcher [failed] 3500ms ------
  Agent:  llm://gpt-4
  Prompt: Execute research
  Input:  art_planner <- planner
  ERROR:  Connection timeout

-- summarizer [skipped] ------
  Blocked by: researcher
```

### JSON (`--json`)

```json
{
  "run_id": "abc123",
  "workflow_name": "research-pipeline",
  "status": "failed",
  "total_nodes": 3,
  "completed_nodes": 2,
  "failed_nodes": 1,
  "duration_ms": 5000,
  "nodes": [...]
}
```

### Rich (`--rich`)

Colored terminal output with panels for each node. Requires the `rich` optional dependency:

```bash
pip install binex[rich]
```

Nodes are displayed in colored panels — green for completed, red for failed, yellow for timed out, dim for skipped. Error messages are highlighted in bold red.

If `rich` is not installed, a clear error message is shown:

```
Error: rich is not installed. Run: pip install binex[rich]
```

## See Also

- [binex run](run.md) -- execute a workflow
- [binex diagnose](diagnose.md) -- automated root-cause analysis
- [binex bisect](bisect.md) -- find divergence between two runs
- [binex trace](trace.md) -- inspect execution traces
- [binex artifacts](artifacts.md) -- inspect artifact contents
