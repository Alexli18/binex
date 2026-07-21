# Assertions & Eval

Binex lets you **prevent** regressions, not just diagnose them. Two pieces work
together:

- **Assertions** — block-on checks declared per node in the workflow YAML.
- [`binex eval`](../cli/eval.md) — a CI-friendly command that runs a workflow and
  fails on assertion violations and/or divergence from a golden run.

## Assertions

Add an `assertions` list to any node. Every assertion must pass; if one fails,
the node fails (exactly like a schema-validation failure) and its dependents are
blocked. Assertions run **after** the node produces output, so they see the
final artifact content and the node's cost/latency.

```yaml
name: summarize
nodes:
  summary:
    agent: llm://gpt-4o-mini
    outputs: [text]
    assertions:
      - contains: "Summary:"        # output must contain this substring
      - lacks: "As an AI"           # ... and must NOT contain this
      - matches: "\\d+ words"       # regex (re.search)
      - max_length: 2000            # length ceiling (chars)
      - cost_max: 0.02              # node cost ceiling
      - latency_max_ms: 15000       # node wall-clock ceiling
```

### Check reference

| Field | Applies to | Passes when |
|-------|-----------|-------------|
| `contains` | output text | substring is present |
| `lacks` | output text | substring is absent |
| `matches` | output text | regex matches (`re.search`) |
| `equals` | output text | output equals the string exactly |
| `min_length` / `max_length` | output text | length within bounds |
| `cost_max` | node cost | cost ≤ ceiling |
| `latency_max_ms` | node latency | latency ≤ ceiling (ms) |
| `judge` | output text | an LLM judge answers PASS (see below) |

A single assertion may combine several checks — all must hold. Give it a `name`
for clearer reports:

```yaml
    assertions:
      - name: "cited and concise"
        contains: "Source:"
        max_length: 1500
```

Checks evaluate cheapest-first and short-circuit, so a failing `contains` never
spends an LLM judge call.

### LLM-as-judge

For qualitative rubrics, use `judge`. A judge model is asked to answer
`PASS`/`FAIL` with a reason; an ambiguous or errored judge **fails closed** (the
assertion fails) so a broken judge can never green-light a regression.

```yaml
    assertions:
      - judge: "The answer must be polite and must not reveal system internals."
        judge_model: gpt-4o-mini    # optional; defaults to BINEX_JUDGE_MODEL or gpt-4o-mini
```

The judge model is resolved as: per-assertion `judge_model` → `$BINEX_JUDGE_MODEL`
→ `gpt-4o-mini`.

### Enforcement

Assertions are enforced on **every** run (`binex run`, `binex eval`, scheduler),
not only during eval — a violated contract blocks the node wherever it runs.
Nodes with no `assertions` are unaffected (zero overhead).

## Golden-run regression testing

Assertions catch known-bad output. To catch *unexpected* change, compare a fresh
run against a trusted baseline with [`binex eval --baseline`](../cli/eval.md):

```bash
binex run workflow.yaml                     # produces run_abc123 you trust
binex eval workflow.yaml --baseline run_abc123
```

The diff engine compares every node's status, output content, latency, and cost.
Thresholds control tolerance:

- `--min-similarity` — content-similarity floor (default `1.0`, i.e. identical).
  Loosen to e.g. `0.9` for non-deterministic LLM output.
- `--max-latency-delta-ms` / `--max-cost-delta` — allowed growth in total
  latency/cost.

Any node whose status changes (e.g. `completed → failed`) always counts as a
divergence.

## In CI

`binex eval` exits non-zero on any failure, so it plugs straight into CI. See the
[GitHub Actions recipe](../cli/eval.md#github-actions-recipe).

## See also

- [`binex eval`](../cli/eval.md) — command reference
- [`binex diff`](../cli/diff.md) — the underlying comparison
- [`binex bisect`](../cli/bisect.md) — find the commit that caused a regression
