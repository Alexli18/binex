# binex diff

## Synopsis

```
binex diff RUN_A RUN_B [OPTIONS]
```

## Description

Compare two runs side-by-side. Highlights differences in node status, latency, and artifact content between runs. Useful after `binex replay` to see what changed.

## Options

| Option | Type | Description |
|---|---|---|
| `RUN_A` | `string` | First run ID |
| `RUN_B` | `string` | Second run ID |
| `--json-output` / `--json` | flag | Output as JSON |

## Example

```bash
# Compare original run with a replay
binex diff abc123 d4e5f6a7

# Machine-readable output
binex diff abc123 d4e5f6a7 --json
```

## Output

The human-readable output shows a formatted diff of each node's status, latency, and artifact changes between the two runs.

With `--json`, the output is a JSON object containing the full structured diff.

## See Also

- [binex replay](replay.md) -- create a forked run to compare
- [binex trace](trace.md) -- inspect individual runs
