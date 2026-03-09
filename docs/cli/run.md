# binex run / binex cancel

## Synopsis

```
binex run [OPTIONS] WORKFLOW_FILE
binex cancel RUN_ID
```

## Description

`binex run` executes a workflow definition. It loads the YAML file, validates DAG structure, registers adapters for all referenced agents (`local://`, `llm://`, `a2a://`), and runs nodes in dependency order. Exits `0` on success, `1` on failure.

`binex cancel` marks a running workflow as cancelled.

## Options

### run

| Option | Type | Description |
|---|---|---|
| `WORKFLOW_FILE` | `Path` (must exist) | Workflow YAML file to execute |
| `--var` | `key=value` (repeatable) | Variable substitution passed to `${user.*}` |
| `--json-output` / `--json` | flag | Output as JSON |
| `--verbose` / `-v` | flag | Show `[N/total]` progress, input arrows, and artifact contents after each step |

### cancel

| Option | Type | Description |
|---|---|---|
| `RUN_ID` | `string` | ID of the run to cancel |

## Example

```bash
# Run a workflow with a user variable
binex run examples/simple.yaml --var input="hello world"

# Run with JSON output and verbose logging
binex run examples/simple.yaml --var input="hello" --json -v

# Cancel a running workflow
binex cancel abc123-run-id
```

## Output

```
Run ID: f7a1b2c3-...
Workflow: simple-pipeline
Status: completed
Nodes: 2/2 completed
```

When a node fails, errors are printed to stderr:

```
  [consumer] Error: connection timeout
Failed: 1
```

### Verbose output (`-v`)

```
[1/2] producer ...
  [producer] -> result:
{'msg': 'no input'}

  [2/2] consumer ...
        <- producer
  [consumer] -> result:
{'art_producer': {'msg': 'no input'}}

Run ID: abc123
Workflow: simple-pipeline
Status: completed
Nodes: 2/2 completed
```

When a run fails, a tip is shown:

```
Tip: run 'binex debug abc123' for full details
```

## See Also

- [binex validate](validate.md) -- check workflow before running
- [binex debug](debug.md) -- post-mortem inspection of a run
- [binex trace](trace.md) -- inspect execution after a run
- [binex replay](replay.md) -- re-run from a specific step
