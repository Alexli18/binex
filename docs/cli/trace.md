# binex trace

## Synopsis

```
binex trace [timeline] RUN_ID [OPTIONS]
binex trace node RUN_ID STEP [OPTIONS]
binex trace graph RUN_ID [OPTIONS]
```

## Description

Inspect execution traces for a completed or in-progress run. The `trace` group has three subcommands. Passing a bare `RUN_ID` without a subcommand defaults to `timeline`.

- **timeline** -- chronological list of all executed steps.
- **node** -- detailed view of a single step including inputs, outputs, prompt, and model.
- **graph** -- ASCII DAG visualization with status icons (`[+]` completed, `[x]` failed).

## Options

### trace timeline (default)

| Option | Type | Description |
|---|---|---|
| `RUN_ID` | `string` | Run to inspect |
| `--json-output` / `--json` | flag | Output as JSON |

### trace node

| Option | Type | Description |
|---|---|---|
| `RUN_ID` | `string` | Run to inspect |
| `STEP` | `string` | Node/step ID within the run |
| `--json-output` / `--json` | flag | Output as JSON |

### trace graph

| Option | Type | Description |
|---|---|---|
| `RUN_ID` | `string` | Run to inspect |
| `--json-output` / `--json` | flag | Output as JSON |

## Example

```bash
# Default timeline view
binex trace abc123

# Detailed node inspection
binex trace node abc123 producer

# ASCII DAG
binex trace graph abc123 --json
```

## Output

`trace node` output:

```
Step: producer
Agent: local://echo
Status: completed
Latency: 42ms
Timestamp: 2026-03-08T10:15:30
Inputs: art_init
Outputs: art_producer
Prompt: Summarize the data
Model: ollama/llama3
```

`trace graph` output:

```
DAG:
[+] producer (local://echo)
  |
  [+] consumer (local://echo)
```

## See Also

- [binex run](run.md) -- execute a workflow
- [binex diff](diff.md) -- compare two runs
- [binex artifacts](artifacts.md) -- inspect artifact contents
