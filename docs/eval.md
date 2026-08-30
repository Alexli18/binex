# Eval — Regression Testing for Agent Pipelines

`binex eval` lets you define declarative test suites that run your workflows, compare outputs against blessed baselines, and produce CI-friendly verdicts. No API keys required for local workflows.

## Quick Start

```bash
# 1. Run the bundled example suite (local:// agents only)
binex eval run examples/eval/research-eval.yaml
# → all cases report "no_baseline" (asserts still checked), exit 0

# 2. Bless the latest runs as baselines
binex eval bless examples/eval/research-eval.yaml

# 3. Re-run — now compared against baselines
binex eval run examples/eval/research-eval.yaml
# → PASS table, exit 0

# 4. Break the workflow, re-run
binex eval run examples/eval/research-eval.yaml
# → FAIL: min_similarity violated, exit 1
```

## Suite YAML Reference

```yaml
name: my-pipeline-eval        # required — baseline/result key
workflow: workflow.yaml        # required — resolved relative to suite file

thresholds:                    # optional suite-level defaults
  min_similarity: 0.85         # float 0.0–1.0
  max_cost_delta: 0.10         # float ≥ 0, absolute USD
  max_latency_delta_ms: 30000  # int ≥ 0 ms

cases:
  - id: my-case                # required, unique
    inputs:                    # optional — passed to human:// nodes / ${user.*}
      topic: "quantum physics"
    thresholds:                # optional — overrides suite thresholds field-by-field
      min_similarity: 0.90
    asserts:                   # optional — per-case assertions
      - type: contains
        node: researcher       # optional — default: terminal node(s)
        value: "quantum"
      - type: not_contains
        value: "error"
      - type: regex
        pattern: "\\d{4}"
      - type: json_path
        path: "$.questions"
        exists: true
      - type: llm_judge        # requires API key for the judge model
        prompt: "Does the answer cite a source?"
        model: "ollama/llama3.2"
```

## Verdict Semantics

| Verdict | Meaning |
|---------|---------|
| `pass` | All asserts passed and all thresholds satisfied |
| `fail` | Any assert failed/errored, or any threshold violated, or workflow errored |
| `no_baseline` | No baseline run blessed yet; asserts still evaluated |

`no_baseline` counts as success (exit 0) unless `--strict-baseline` is set.

### How `min_similarity` is measured

The threshold compares the candidate run against its baseline with the same engine as [`binex diff`](cli/diff.md), so it follows the shape of each node's output:

- **Structured output** (a mapping or list) is compared **field by field**: similarity is the fraction of leaf fields that are unchanged. Reordering keys is not a difference.
- **Text output** uses a character-level `difflib` ratio.

!!! warning "This changed — re-check thresholds tuned before 2026-08"
    Structured output used to be stringified and scored character-wise, which is close to orthogonal to whether anything meaningful changed. Measured on the same inputs:

    | Case | Old | New |
    |---|---:|---:|
    | Reordered keys, same mapping | 0.6304 | 1.0000 |
    | One field of ten changed | 0.9858 | 0.9000 |
    | One field changed, long text field alongside | 0.9991 | 0.5000 |

    The first row removes false failures: a strict suite no longer breaks because a model emitted the same JSON with keys in another order. The other two are the reason to re-check your numbers — a real regression that a character ratio diluted to 0.99 now scores proportionally, so a suite with `min_similarity: 0.95` that used to pass on a changed field will now fail. That is the intended behaviour, but it is a behaviour change: review suite thresholds and re-bless baselines where the new score is correct.

    Text-output thresholds are unaffected.

## CLI Commands

### `binex eval run <suite.yaml>`

```
Options:
  --parallel N          Run N cases concurrently (default: 1)
  --json                Output full EvalResult as JSON
  --format github       Emit GitHub Actions annotations (::error / ::warning)
  --strict-baseline     Exit 1 if any case has no baseline
```

**Exit codes**: `0` = all pass (or no_baseline without --strict-baseline); `1` = any fail; `2` = suite invalid.

### `binex eval bless <suite.yaml>`

```
Options:
  --case <id>    Bless only this case
  --run <id>     Use a specific run id
  --force        Skip suite+case tag verification
```

### `binex eval baselines <suite.yaml>`

```
Options:
  --json    Output as JSON
```

Lists current baseline run ids per case. Exit 0 always (informational).

## CI Recipe (GitHub Actions)

```yaml
- name: Eval regression suite
  run: |
    binex eval run examples/eval/research-eval.yaml \
      --format github \
      --strict-baseline
```

Failed cases produce `::error` annotations; cases without baselines produce `::warning` annotations.

## Web UI

Navigate to **Analyze → Eval** in the `binex ui` dashboard to:

- Browse recent eval executions
- See per-case pass/fail grid
- Click a failed case to open the diff view (`baseline_run_id` vs `run_id`)

## Assumptions & Limitations

- **Baselines live in SQLite**: `baseline_run_id` in YAML is tolerated but ignored.
- **`llm_judge` requires a model**: no default judge model is contacted implicitly.
- **Sequential by default**: use `--parallel N` for faster suites.
- **Non-interactive only**: `human://` nodes are driven by `inputs` in the case definition.
