# Dynamic fan-out (`foreach`)

`scatter` fixes the number of branches at load time. Real workloads decide it at
runtime — a planner LLM picks the subtasks, a file lister finds 600 episodes, a
designer agent decides "12 sprites and 3 tracks". A `foreach` node expands at
runtime, one worker per item produced by a mapper node.

```yaml
name: translate-pipeline
nodes:
  plan:
    agent: "llm://gpt-4o"
    outputs: [chunks]
    output_schema: { type: array }        # the mapper emits an array

  translate:
    foreach: plan                          # one worker per array element
    agent: "llm://gemini-flash"
    outputs: [text]
    max_parallel: 5
    on_item_failure: continue              # or fail_fast
```

## How it works

The DAG stays static. `translate` is a single placeholder node that depends on
`plan` (the dependency is added for you). When `plan` completes and its array
output exists, `translate` **expands at runtime** into:

- one **worker** per item — a clone of the `foreach` node, receiving that single
  item as its input artifact; and
- one **aggregator** (`translate::aggregate`) that collects the workers' outputs.

Any node that depended on `translate` is rewired to depend on the aggregator, so
downstream logic is unchanged. The scheduler itself doesn't become dynamic — it
just sees "more nodes appeared", reusing the same battle-tested execution path.

## Fields

| Field | Default | Description |
|---|---|---|
| `foreach` | — | Node ID of the mapper whose array output drives expansion |
| `max_parallel` | — | (reserved) worker concurrency hint |
| `max_items` | `100` | Hard cap — expansion fails if the mapper returns more |
| `on_item_failure` | `continue` | `continue` (aggregate successes + failures) or `fail_fast` |
| `item_key` | — | JSONPath (e.g. `$.id`) giving each item a stable identity |

## Guardrails (mandatory, up-front)

An LLM mapper can return 10 000 items — by bug or prompt injection. Before *any*
worker runs, `foreach`:

- enforces `max_items` (default 100) — over the cap, the node fails with a clear
  message instead of exploding the run; and
- estimates the batch cost from the node's per-item budget hint and checks it
  against the workflow budget — *"expanding 600 workers (est. $18) would exceed
  budget $10"* stops the run before it starts spending.

## Partial failure

With `on_item_failure: continue` (the default), a worker that fails does **not**
fail the run. The aggregator's output records what happened:

```json
{
  "results": [ ...successful worker outputs... ],
  "total": 600,
  "succeeded": 597,
  "failed": ["translate::a1b2c3", "translate::d4e5f6", "translate::0789ab"]
}
```

With `fail_fast`, the first worker failure blocks the aggregator and the run
fails — use it when partial results are useless.

## Item identity

Workers are keyed by **content hash** (or the `item_key` JSONPath), not list
index. `translate[17]` would be a bad identity — indices shift when the list
changes. Content keying means node cache (#68) and cross-run diff still match
"episode 42" even if it moved in the list.

## Out of scope (v1)

- **Nested `foreach`** — a foreach worker that is itself a foreach.
- **Arbitrary agent-decided branching** — that's a different tool's territory.
- **Streaming expansion** — starting workers while the mapper is still emitting.

## See also

- [`binex run`](../cli/run.md) — running workflows
- Node caching (`binex run --cache`) — pairs with content-keyed workers
