# binex bisect

## Synopsis

```
binex bisect <GOOD_RUN_ID> <BAD_RUN_ID> [OPTIONS]   # across nodes (default)
binex bisect history -w <WORKFLOW> --good <REF> --bad <REF> [OPTIONS]
```

`binex bisect` finds a regression at two granularities:

- **Across nodes** (default) — given a good and a bad *run*, find the first node where they diverge.
- **Across git history** (`history`) — given a good and a bad *commit*, find the commit that broke the workflow, then hand off to the node-level bisect to locate the offending node within it.

The bare `binex bisect <good> <bad>` form is unchanged and still routes to the node-level bisect.

## Description (node-level)

Find the divergence point between two runs. Compares runs node-by-node, classifying each as a match, status difference, or content difference. Identifies the first node where the two runs diverge — helping you pinpoint where a regression or behavior change was introduced.

### What counts as a difference

Status is compared first and exactly: a node that failed in one run and completed in the other is always the divergence, with no text involved.

For nodes that completed in both runs, the comparison depends on the shape of the artifact content:

**Structured content** (a mapping or list — the usual shape of `Artifact.content`) is compared **field by field**. Reordering keys is not a difference; a changed, added, or removed field is, and the output names it:

```text
└── reviewer     ⚠ changed    1200ms → 1200ms  ← root cause
   └── decision: 'approved' -> 'rejected'
```

Similarity is the fraction of leaf paths (union of both sides) that are unchanged, so `--threshold` still applies: two of three fields equal gives `0.667`.

**Text content** falls back to a character-level ratio (`difflib.SequenceMatcher`).

!!! warning "The text ratio is a weak signal on LLM output"
    It measures how many *characters* moved, which is close to orthogonal to whether the meaning changed — and on the highest-stakes cases it is anti-correlated. Rewording moves many characters while preserving meaning (scores ~0.44, flagged); inserting a single "not" inverts the meaning while moving almost nothing (scores ~0.98, passed). The effect worsens with length: the same `12% -> 21%` edit scores `0.982` in a short artifact and `0.999` in a 1 300-character one.

    No threshold separates these two error classes — they sit on opposite sides of it. For prose, prefer [`binex diff --semantic`](diff.md), which asks a model narrow questions about structure and facts instead of counting characters. Emitting structured output (JSON) from your nodes is the cheaper fix: it puts them on the field-wise path above, which is exact and free.

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

For a `content_diff`, the `content_diff` field of the node entry holds one line per changed field when the content was structured (`decision: 'approved' -> 'rejected'`), or unified-diff lines when it was text.

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

## `binex bisect history`

Binary-search git history for the commit that broke pipeline quality — a `git bisect run` for agent workflows.

Binex owns the workflow spec *and* the launch, so given "quality dropped sometime this week" it can walk the commit history, re-run the workflow at each probe commit, and identify the offending commit. Each probe runs in an isolated **git worktree**, so your working tree and `HEAD` are never touched.

### Synopsis

```
binex bisect history -w <WORKFLOW> --good <REF> --bad <REF> [OPTIONS]
```

### How it works

1. Resolves `--good` / `--bad` to commits (a git ref, or a **run ID** — resolved to the commit that run recorded, see [`binex debug`](debug.md) `git_sha`).
2. Lists commits on the good→bad ancestry path.
3. Binary-searches them: at each probe it checks the commit out in a temporary worktree and runs the workflow **as it existed at that commit**, judging pass/fail with the same criterion as [`binex eval`](eval.md) — the workflow's own assertions, plus an optional `--baseline` diff.
4. Reports the first bad commit. A commit whose workflow file is missing, or that can't be evaluated, is **skipped** (never falsely blamed).

Node caching ([`binex run --cache`](run.md)) makes this affordable: typically one prompt changed per commit, so only affected nodes re-execute.

### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `-w, --workflow` | path | required | Workflow file to run at each probed commit |
| `--good` | ref/run | required | Known-good commit/ref, or a run ID |
| `--bad` | ref/run | required | Known-bad commit/ref, or a run ID |
| `--var KEY=VALUE` | string | — | Variable substitution (repeatable) |
| `--baseline RUN_ID` | string | — | Golden run for a diff criterion (else assertions only) |
| `--min-similarity` | float | `1.0` | Content-similarity floor when `--baseline` is used |
| `--max-latency-delta-ms` | float | — | Latency-growth ceiling when `--baseline` is used |
| `--max-cost-delta` | float | — | Cost-growth ceiling when `--baseline` is used |
| `--json` | flag | false | Machine-readable output |

### Exit codes

| Code | Meaning |
|---|---|
| 0 | A bad commit was found |
| 1 | No bad commit found, or indeterminate (too many commits skipped) |
| 2 | Setup error (not a repo, unknown ref, bad range) |

### Example

```bash
binex bisect history -w flow.yaml --good v1.0 --bad HEAD
```

```
  probe 858ac92257e9: bad — n1: assertion failed: contains='...'
  probe 922df37a181c: good — eval passed
Tested 2 commit(s), 0 skipped.

✗ First bad commit: 858ac92257e978dc65ca9072e6f585aac5824a98
  n1: assertion failed: contains='...'

Tip: run 'binex bisect <good_run> <bad_run>' to locate the offending node within that commit.
```

## See Also

- [binex eval](eval.md) -- the pass/fail criterion used by history bisect
- [binex diagnose](diagnose.md) -- root-cause analysis for failures
- [binex diff](diff.md) -- side-by-side run comparison
- [binex debug](debug.md) -- post-mortem inspection (shows the run's commit)
- [binex replay](replay.md) -- re-run with modifications
