# binex replay

## Synopsis

```
binex replay RUN_ID --from STEP --workflow FILE [OPTIONS]
```

## Description

Replay a previous run starting from a specific step. Artifacts produced before `--from` are reused; nodes from that step onward are re-executed. Use `--agent` to swap agent implementations for individual nodes (e.g., replace a production LLM with a local model for debugging).

Exits `0` on success, `1` on failure.

## Options

| Option | Type | Description |
|---|---|---|
| `RUN_ID` | `string` | Original run to fork from |
| `--from` | `string` (required) | Step ID to re-execute from |
| `--workflow` | `Path` (required, must exist) | Workflow YAML file |
| `--agent` | `node=agent` (repeatable) | Swap agent for a node |
| `--json-output` / `--json` | flag | Output as JSON |

## Example

```bash
# Replay from the consumer step
binex replay abc123 --from consumer --workflow examples/simple.yaml

# Replay with an agent swap
binex replay abc123 \
  --from consumer \
  --workflow examples/simple.yaml \
  --agent consumer=llm://ollama/llama3
```

## Output

```
Replay Run ID: d4e5f6a7-...
Forked from: abc123 at step 'consumer'
Workflow: simple-pipeline
Status: completed
Nodes: 2/2 completed
```

## See Also

- [binex run](run.md) -- execute a fresh workflow
- [binex diff](diff.md) -- compare original and replayed runs
- [binex trace](trace.md) -- inspect the replayed run
