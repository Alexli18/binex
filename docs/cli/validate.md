# binex validate

## Synopsis

```
binex validate [OPTIONS] WORKFLOW_FILE
```

## Description

Validate a workflow YAML file without executing it. Performs three phases of checks:

1. **YAML parsing** -- file loads as valid YAML and conforms to the workflow schema.
2. **DAG structure** -- node dependencies form a valid directed acyclic graph (no cycles, no missing refs).
3. **Agent refs** -- all agent URIs use a recognized prefix (`local://`, `llm://`, `a2a://`).

Exits `0` if valid, `2` if errors are found.

## Options

| Option | Type | Description |
|---|---|---|
| `WORKFLOW_FILE` | `Path` (must exist) | Workflow YAML file to validate |
| `--json-output` / `--json` | flag | Output as JSON |

## Example

```bash
binex validate examples/simple.yaml

binex validate examples/simple.yaml --json
```

## Output

On success:

```
Workflow 'simple-pipeline' is valid.
  Nodes:  2
  Edges:  1
  Agents: local://echo
```

On failure:

```
Error: Cycle detected in DAG: consumer -> producer -> consumer
```

JSON output on success:

```json
{
  "valid": true,
  "node_count": 2,
  "edge_count": 1,
  "agents": ["local://echo"]
}
```

## See Also

- [binex run](run.md) -- execute a validated workflow
- [binex scaffold](scaffold.md) -- generate agent templates
