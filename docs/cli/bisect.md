# binex bisect

## Synopsis

```
binex bisect <GOOD_RUN_ID> <BAD_RUN_ID> [OPTIONS]
```

## Description

Find the divergence point between two runs. Compares runs node-by-node, classifying each as a match, status difference, or content difference. Identifies the first node where the two runs diverge — helping you pinpoint where a regression or behavior change was introduced.

The comparison uses content similarity (via `difflib.SequenceMatcher`) to detect subtle output differences even when both nodes completed successfully.

## Arguments

| Argument | Required | Description |
|---|---|---|
| `GOOD_RUN_ID` | Yes | The "known good" run (baseline) |
| `BAD_RUN_ID` | Yes | The "known bad" run (comparison) |

## Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--threshold` | `float` | `0.9` | Content similarity threshold (0.0-1.0). Nodes with similarity below this are flagged as `content_diff` |
| `--diff` | flag | false | Show full unified diffs instead of content preview |
| `--json` | flag | false | Output as JSON |
| `--rich / --no-rich` | flag | auto | Rich formatted output (auto-detected if `rich` is installed) |

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Run not found |

## Examples

```bash
# Find where two runs diverge
binex bisect run_good run_bad

# Stricter content comparison
binex bisect run_good run_bad --threshold 0.95

# Show full diffs for changed nodes
binex bisect run_good run_bad --diff

# JSON for scripting
binex bisect run_good run_bad --json
```

## Output

### Plain text (default)

```
Bisecting: run_good vs run_bad

  planner       match
  researcher    match
  validator     content_diff  (similarity: 0.72)
    Good: {"validated": 9, "papers": [...]}
    Bad:  {"validated": 5, "papers": [...]}
  summarizer    status_diff   (completed -> failed)

Verdict: First divergence at 'validator'
  3 of 4 nodes compared
  1 content diff, 1 status diff
```

### Rich (`--rich`)

The rich output includes:

- **Verdict Card** — highlights the first divergence node with status
- **Pipeline Tree** — visual node-by-node comparison with colored icons:
  - Green checkmark for matches
  - Yellow warning for content differences
  - Red cross for status differences
- **Footer** with summary statistics

### JSON (`--json`)

```json
{
  "good_run": "run_good",
  "bad_run": "run_bad",
  "threshold": 0.9,
  "verdict": {
    "node_id": "validator",
    "type": "content_diff",
    "similarity": 0.72
  },
  "nodes": [
    {
      "node_id": "planner",
      "status": "match",
      "status_good": "completed",
      "status_bad": "completed",
      "similarity": 1.0
    },
    {
      "node_id": "researcher",
      "status": "match",
      "status_good": "completed",
      "status_bad": "completed",
      "similarity": 0.98
    },
    {
      "node_id": "validator",
      "status": "content_diff",
      "status_good": "completed",
      "status_bad": "completed",
      "similarity": 0.72
    },
    {
      "node_id": "summarizer",
      "status": "status_diff",
      "status_good": "completed",
      "status_bad": "failed"
    }
  ]
}
```

## Node Comparison Statuses

| Status | Meaning |
|--------|---------|
| `match` | Same status and content similarity above threshold |
| `content_diff` | Same status but content similarity below threshold |
| `status_diff` | Different execution status (e.g., completed vs failed) |

## Use Cases

### Debugging a Regression

After a workflow that was working starts failing:

```bash
# Find the last good run and the failing run
binex bisect run_last_good run_failing
```

The verdict tells you exactly which node started behaving differently.

### Comparing Model Swaps

After replaying a run with a different model:

```bash
binex replay run_original --from summarizer --agent summarizer=llm://anthropic/claude-sonnet-4-20250514
# Produces run_new

binex bisect run_original run_new --diff
```

The `--diff` flag shows exactly how the output content changed.

### CI Regression Detection

```bash
RESULT=$(binex bisect "$BASELINE_RUN" "$CURRENT_RUN" --json)
VERDICT_TYPE=$(echo "$RESULT" | jq -r '.verdict.type')

if [ "$VERDICT_TYPE" = "status_diff" ]; then
  echo "Status regression detected"
  exit 1
fi
```

## Tips

- Put the "known good" run first and the "bad" run second — the output labels use these terms.
- Use `--threshold 0.95` for stricter comparison when outputs should be nearly identical.
- Use `--threshold 0.5` for looser comparison when you only care about major changes.
- Combine with `binex debug` to inspect the divergent node in detail.

## See Also

- [binex diagnose](diagnose.md) -- root-cause analysis for failures
- [binex diff](diff.md) -- side-by-side run comparison
- [binex debug](debug.md) -- post-mortem inspection
- [binex replay](replay.md) -- re-run with modifications
