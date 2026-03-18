# Loop Containers

## What is a Loop Container?

A loop container is a special node type that iteratively executes a group of child nodes until an exit condition is met. This enables **iterative refinement pipelines** — workflows where an agent generates output, evaluates it, and refines it over multiple passes.

```yaml
nodes:
  refine_loop:
    type: loop
    agent: "loop://container"
    outputs: [refined_output]
    loop:
      exit:
        field: "$.score"
        operator: ">="
        value: 8.0
      max_iterations: 5
      timeout_minutes: 10
      accumulate: false
      contains:
        - generate
        - evaluate
        - refine

  generate:
    agent: "llm://openai/gpt-4o"
    system_prompt: "Generate a draft based on the input"
    inputs:
      topic: "${user.topic}"
    outputs: [draft]

  evaluate:
    agent: "llm://openai/gpt-4o"
    system_prompt: "Score the draft from 1-10. Return JSON: {\"score\": N, \"feedback\": \"...\"}"
    inputs:
      draft: "${generate.draft}"
    outputs: [evaluation]
    depends_on: [generate]

  refine:
    agent: "llm://openai/gpt-4o"
    system_prompt: "Improve the draft based on feedback"
    inputs:
      draft: "${generate.draft}"
      feedback: "${evaluate.evaluation}"
    outputs: [improved]
    depends_on: [evaluate]
```

In this example, the `refine_loop` container runs `generate → evaluate → refine` repeatedly until the evaluation score reaches 8.0 or higher.

## Loop Types

| Type | Status | Description |
|------|--------|-------------|
| **While loop** | v1 (current) | Repeats until exit condition is met or limits exceeded |
| **For-each loop** | v2 (planned) | Iterates over a list of items |

## Exit Condition

The exit condition is evaluated after each iteration against the output of the last node in the loop. It uses JSONPath to extract a value and compare it with an operator.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `field` | `str` | yes | JSONPath expression (must start with `$.`) |
| `operator` | `str` | yes | Comparison operator |
| `value` | `float`, `str`, or `bool` | yes | Value to compare against |

### Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `>=` | `$.score >= 8.0` | Greater than or equal |
| `<=` | `$.score <= 0.1` | Less than or equal |
| `>` | `$.confidence > 0.9` | Greater than |
| `<` | `$.error_rate < 0.05` | Less than |
| `==` | `$.status == "approved"` | Equal (works with strings and numbers) |
| `!=` | `$.status != "needs_revision"` | Not equal |

### JSONPath Examples

The JSONPath expression uses dot notation to access nested fields in the output artifact:

```yaml
# Simple field
exit:
  field: "$.score"
  operator: ">="
  value: 8.0

# Nested field
exit:
  field: "$.result.quality"
  operator: ">="
  value: 0.95

# String comparison
exit:
  field: "$.status"
  operator: "=="
  value: "approved"

# Boolean check
exit:
  field: "$.is_valid"
  operator: "=="
  value: true
```

The exit condition checks the last node's output artifact. If the artifact is a JSON string, it is parsed first. If the JSONPath field is not found, the condition evaluates to `false` and the loop continues.

## Loop Configuration

### `max_iterations`

Maximum number of iterations before the loop stops. Default: `5`. Must be >= 1.

When the loop reaches `max_iterations` without the exit condition being met, a `MaxIterationsExceededError` is raised and the loop node is marked as failed.

```yaml
loop:
  exit:
    field: "$.score"
    operator: ">="
    value: 9.0
  max_iterations: 10  # allow up to 10 attempts
```

### `timeout_minutes`

Optional wall-clock timeout for the entire loop. If the loop exceeds this time, a `LoopTimeoutExceededError` is raised and the loop node is marked as failed.

```yaml
loop:
  exit:
    field: "$.score"
    operator: ">="
    value: 8.0
  max_iterations: 20
  timeout_minutes: 15  # stop after 15 minutes regardless
```

### `accumulate`

Controls how iteration outputs are collected. Default: `false`.

| Value | Behavior |
|-------|----------|
| `false` | Only the last iteration's output is returned. Each iteration receives the previous iteration's output as input. |
| `true` | All iteration outputs are combined into a single artifact of type `loop_accumulated` with the structure `{"iterations": [...]}`. |

**Accumulated output example:**

```json
{
  "iterations": [
    {"iteration": 1, "artifact_id": "abc", "type": "text", "content": "..."},
    {"iteration": 2, "artifact_id": "def", "type": "text", "content": "..."},
    {"iteration": 3, "artifact_id": "ghi", "type": "text", "content": "..."}
  ]
}
```

### `contains`

List of node IDs that are part of the loop. These nodes are excluded from the top-level DAG and executed within the loop container.

```yaml
loop:
  contains:
    - generate
    - evaluate
    - refine
```

## State Between Iterations

In non-accumulate mode (default), the output of the last node in the current iteration becomes the input for the entry nodes of the next iteration. This creates a natural refinement chain where each iteration builds on the previous result.

Entry nodes (nodes with no internal dependencies) receive the loop's input artifacts on the first iteration, and the previous iteration's output on subsequent iterations.

## Execution Model

When the orchestrator encounters a loop node, it delegates to `LoopExecutor`:

1. **Start** — emits `loop:started` event
2. **Each iteration:**
   - Creates an internal `Scheduler` for the child nodes
   - Distributes input artifacts to entry nodes
   - Executes child nodes in topological order
   - Checks the exit condition against the last node's output
   - Emits `loop:iteration` event with iteration number
3. **Exit** — emits `loop:completed` when exit condition is met

### Execution Records

Each inner node execution creates an `ExecutionRecord` with:

- **Task ID format**: `{loop_node_id}.{node_id}` (dotted notation)
- **`iteration_number`**: 1-based iteration index (e.g., 1, 2, 3...)

This allows debugging and cost tracking at the per-node, per-iteration level.

### Cost Tracking

Costs are tracked individually for each inner node execution. The total cost of a loop container is the sum of all inner node costs across all iterations. Per-node budgets are enforced within each iteration.

## Limitations (v1)

- **No nested loops** — a loop container cannot contain another loop container
- **No cross-loop dependencies** — nodes inside one loop cannot depend on nodes inside another loop
- **No pass-through** — loop nodes cannot be used as simple pass-through without child nodes
- **Single exit condition** — only one exit condition per loop (no AND/OR combinations)
- **Dot notation only** — JSONPath supports `$.field.nested` but not array indexing or filters

## Debugging Loops

### CLI

Use `binex debug <run-id>` to inspect loop executions. Execution records for inner nodes include the `iteration_number` field, so you can trace each iteration separately.

### Web UI

The Web UI shows loop containers with:

- **Loop Container Node** — dashed border with iteration badge showing current/max iterations
- **Exit Condition Display** — shows the JSONPath condition (e.g., `$.score >= 8.0`)
- **Iterations Panel** — accordion view with per-iteration node statuses, latencies, and costs
- **Runtime Badge** — live iteration counter during execution

### Loops API

Two API endpoints are available for programmatic access:

- `GET /api/v1/loops/{run_id}` — all loops in a run with iteration details
- `GET /api/v1/loops/{run_id}/{loop_node_id}` — specific loop detail

## Related Concepts

- [Workflows](workflows.md) — loops are defined within workflow YAML
- [Execution](execution.md) — loop iterations create execution records with `iteration_number`
- [Artifacts](artifacts.md) — each iteration produces artifacts linked by lineage
- [Workflow Format](../workflows/format.md#loop-container) — YAML schema for loop nodes
