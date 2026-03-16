# binex list

## Synopsis

```
binex list [OPTIONS]
```

## Description

Discover available workflows in the current directory and bundled examples. Scans for `.yaml`/`.yml` files that contain a `nodes` key (valid Binex workflows) and displays them with name, node count, and description.

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--json` | flag | `false` | Output as JSON (machine-readable) |

## Output

The command displays two groups:

- **Local workflows** — `.yaml`/`.yml` files in the current working directory
- **Examples** — bundled example workflows from the `examples/` directory

For each workflow, shows:
- **Name** — from the `name` field in YAML, or filename stem
- **Nodes** — number of nodes in the workflow
- **Description** — from the `description` field in YAML
- **Path** — file path

If no local workflows are found, displays a tip to run `binex start`.

## Examples

```bash
# List all available workflows
binex list

# Output as JSON (for scripting)
binex list --json
```

### Sample output

```
Local workflows:
  my-pipeline (4 nodes) — Research and summarize
    ./workflow.yaml

Examples (29):
  simple (2 nodes) — Minimal two-node pipeline
    examples/simple.yaml
  diamond-example (4 nodes) — Diamond DAG pattern: A -> (B, C) -> D
    examples/diamond.yaml
  ...
```

### JSON output

```json
{
  "local": [
    {
      "path": "./workflow.yaml",
      "name": "my-pipeline",
      "description": "Research and summarize",
      "nodes": 4
    }
  ],
  "examples": [
    {
      "path": "examples/simple.yaml",
      "name": "simple",
      "description": "Minimal two-node pipeline",
      "nodes": 2
    }
  ]
}
```

## See Also

- [`binex start`](start.md) — Create a new workflow interactively
- [`binex run`](run.md) — Execute a workflow
- [`binex scaffold`](scaffold.md) — Generate workflow from DSL
