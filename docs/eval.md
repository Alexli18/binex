# Eval — Regression Testing for Agent Pipelines

Binex lets you **prevent** regressions, not just diagnose them. There are two ways in, and they are for different jobs.

## Which one do I want?

| | **Node assertions** | **Eval suites** |
|---|---|---|
| Written in | the workflow YAML, per node | a separate `suite.yaml`, per case |
| Enforced | on **every run** — a failed assertion fails the node | only when you run the suite |
| Reference run | `binex eval golden --baseline` | `binex eval bless` |
| Use it for | invariants that must always hold ("never emits an apology") | a matrix of inputs graded against known-good outputs |
| Command | [`binex eval golden`](#node-assertions) | [`binex eval run`](#eval-suites) |

They are not alternatives — a workflow with node assertions can also be driven by a suite, and the suite inherits the assertion failures.

!!! note "The same check means the same thing in both"
    `contains`, `regex` and the LLM judge share one implementation, and artifact content is rendered the same way for both: **JSON** for mappings and lists. Before 2026-08 the two used `json.dumps` and Python's `str()` respectively, so for `{"decision": "approved"}` a `contains: '"decision"'` passed in a suite and failed as a node assertion, and `contains: "'decision'"` did the opposite. Node assertions written against the single-quoted form need updating to double quotes.

A blessed baseline and a golden run are the same thing — one stored reference run. `binex eval golden --baseline SUITE:CASE` uses a baseline blessed with `binex eval bless`, and `binex eval bless --run <id>` blesses any run.

## Eval suites

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

---

## Node assertions

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
run against a trusted baseline with [`binex eval --baseline`](cli/eval.md):

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
[GitHub Actions recipe](cli/eval.md#github-actions-recipe).
