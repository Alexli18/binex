# export

Export run data for external analysis.

## Usage

```bash
binex export <run_id> [options]
```

Export execution data for a specific run to CSV (default) or JSON format.

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `run_id` | yes | Run ID to export (or `latest`) |

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--format` | `csv` | Output format: `csv` or `json` |
| `--output` / `-o` | stdout | Output file path (default: print to terminal) |
| `--last` | — | Export the last N runs instead of a single run |
| `--include-artifacts` | `false` | Include artifact content in the export |

### Examples

```bash
# Export latest run as CSV
binex export latest

# Export as JSON to a file
binex export run_abc123 --format json -o run.json

# Export last 5 runs with artifacts
binex export latest --last 5 --include-artifacts
```

### CSV columns

| Column | Description |
|--------|-------------|
| `run_id` | Run identifier |
| `workflow_name` | Workflow name |
| `status` | Run status |
| `started_at` | Start timestamp |
| `completed_at` | Completion timestamp |
| `total_nodes` | Total node count |
| `completed_nodes` | Successfully completed nodes |
| `failed_nodes` | Failed nodes |
| `total_cost` | Accumulated cost |
