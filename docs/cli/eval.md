# `binex eval`

Run a workflow as a **regression check** and exit non-zero when it fails. This
turns Binex's diff engine from a post-mortem tool into a pre-merge safety net:
drop `binex eval` into CI on any PR that touches workflow YAML or prompts.

`eval` gates on two independent signals:

1. **Node assertions** — block-on checks declared in the workflow YAML (see
   [Assertions](../features/eval.md)). A failed assertion fails the node, which
   fails the run, which fails the eval.
2. **Baseline diff** — with `--baseline <run-id>`, the fresh run is compared
   against a stored "golden" run using the diff engine; divergence beyond the
   configured thresholds fails the eval.

## Usage

```bash
binex eval WORKFLOW_FILE [OPTIONS]
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--var KEY=VALUE` | — | Variable substitution (repeatable) |
| `--baseline RUN_ID` | — | Golden run to diff against |
| `--min-similarity FLOAT` | `1.0` | Content-similarity floor vs the baseline (`1.0` = identical) |
| `--max-latency-delta-ms FLOAT` | — | Fail if total latency grows by more than this |
| `--max-cost-delta FLOAT` | — | Fail if total cost grows by more than this |
| `--gateway URL` | — | A2A Gateway URL for `a2a://` agents |
| `--json`, `--json-output` | off | Emit the report as JSON |

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Run completed and stayed within thresholds — **PASS** |
| `1` | An assertion failed, a node failed, or the run diverged — **FAIL** |
| `2` | Setup error (invalid workflow, missing baseline run) |

## Examples

Enforce a workflow's own assertions (no baseline needed):

```bash
binex eval workflow.yaml
```

Compare against a golden run and require an exact match:

```bash
binex eval workflow.yaml --baseline run_abc123
```

Allow small, expected drift on a non-deterministic (LLM) pipeline:

```bash
binex eval workflow.yaml --baseline run_abc123 \
    --min-similarity 0.9 \
    --max-cost-delta 0.01
```

Machine-readable output for CI:

```bash
binex eval workflow.yaml --baseline run_abc123 --json
```

```json
{
  "run_id": "run_9f2c...",
  "run_status": "completed",
  "baseline_run_id": "run_abc123",
  "node_errors": [],
  "divergences": [],
  "passed": true
}
```

## Recording a golden run

A baseline is just an ordinary run ID. Produce one you trust, then reference it:

```bash
binex run workflow.yaml          # note the printed run_id
binex eval workflow.yaml --baseline <that-run-id>
```

## GitHub Actions recipe

Run evals on every PR that touches the workflow or its prompts:

```yaml
# .github/workflows/binex-eval.yml
name: binex-eval
on:
  pull_request:
    paths:
      - "workflows/**"
      - "prompts/**"
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install binex
      - name: Run workflow evals
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: binex eval workflows/release.yaml
```

The job fails (non-zero exit) the moment an assertion or baseline threshold is
violated, blocking the merge.

## See also

- [Assertions](../features/eval.md) — declaring block-on checks in YAML
- [`binex diff`](diff.md) — the underlying run comparison
- [`binex bisect`](bisect.md) — locate the change that introduced a regression
