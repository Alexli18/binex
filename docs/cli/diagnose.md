# binex diagnose

## Synopsis

```
binex diagnose <RUN_ID> [OPTIONS]
```

## Description

Automated root-cause analysis for a workflow run. Analyzes failed nodes, identifies the root cause of failure, detects cascade effects across the DAG, flags latency anomalies, and generates actionable recommendations.

Use `binex diagnose` after a failed run to quickly understand what went wrong without manually inspecting each node.

## Arguments

| Argument | Required | Description |
|---|---|---|
| `RUN_ID` | Yes | Workflow run identifier |

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--json` | flag | false | Output as JSON |
| `--rich / --no-rich` | flag | auto | Rich formatted output (auto-detected if `rich` is installed) |

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Run not found |

## Examples

```bash
# Diagnose a failed run
binex diagnose run_abc123

# JSON output for scripting
binex diagnose run_abc123 --json

# Force rich output
binex diagnose run_abc123 --rich
```

## Output

### Plain text (default)

```
Run: run_abc123
Status: issues_found

Root Cause: researcher
  Error: Connection timeout
  Pattern: timeout

Affected Nodes: summarizer, formatter

Latency Anomalies:
  planner: 8500ms (4.2x median)

Recommendations:
  - Check network connectivity for node 'researcher'
  - Investigate latency spike in node 'planner'
```

### JSON (`--json`)

```json
{
  "run_id": "run_abc123",
  "status": "issues_found",
  "root_cause": {
    "node_id": "researcher",
    "error_message": "Connection timeout",
    "pattern": "timeout"
  },
  "affected_nodes": ["summarizer", "formatter"],
  "latency_anomalies": [
    {
      "node_id": "planner",
      "latency_ms": 8500,
      "median_ms": 2000,
      "ratio": 4.2
    }
  ],
  "recommendations": [
    "Check network connectivity for node 'researcher'",
    "Investigate latency spike in node 'planner'"
  ]
}
```

### Rich (`--rich`)

Colored panels for each section of the report:

- **Diagnostic Report** panel with run ID and status
- **Root Cause** panel with the failing node, error message, and error pattern
- **Affected Nodes** panel listing cascade-affected downstream nodes
- **Latency Anomalies** table with node, latency, median, and ratio columns
- **Recommendations** panel with actionable suggestions

Requires `pip install binex[rich]`.

## Analysis Details

### Error Pattern Classification

`binex diagnose` classifies errors into patterns:

| Pattern | Detected Keywords |
|---------|-------------------|
| `timeout` | "timeout", "timed out" |
| `rate_limit` | "rate limit" |
| `auth` | "unauthorized", "forbidden", "auth" |
| `budget` | "budget exceeded" |
| `connection` | "connection refused", "connection error" |
| `unknown` | Everything else |

### Cascade Detection

When a node fails, all downstream nodes that depend on it (directly or transitively) are identified as affected. This helps distinguish the root cause from its side effects.

### Latency Anomalies

Nodes with latency exceeding 3x the median latency across all nodes are flagged. This can reveal performance issues even in successful runs.

## See Also

- [binex debug](debug.md) -- detailed post-mortem inspection
- [binex bisect](bisect.md) -- find divergence between two runs
- [binex trace](trace.md) -- execution timeline
