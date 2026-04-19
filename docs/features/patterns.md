# Pattern Nodes

Pattern Nodes are macro-nodes that expand into full sub-DAG pipelines at runtime. Declare a pattern in YAML with a single node; the `PatternExpander` wires up all internal steps before execution begins.

## Quick start

```yaml
name: review_pipeline
nodes:
  fetch:
    agent: llm://gpt-4o-mini
    system_prompt: "Fetch and summarize the document."

  review:
    pattern: critic
    model: gpt-4o
    depends_on: [fetch]
    config:
      rounds: 2

  publish:
    agent: llm://gpt-4o-mini
    system_prompt: "Format the reviewed content for publication."
    depends_on: [review]
```

The `review` node expands into `review.draft → review.critique → review.refine` before the workflow runs. `publish.depends_on` is automatically rewired to `review.refine` (the exit node).

## Declaring a pattern node

```yaml
nodes:
  my_node:
    pattern: <pattern_type>       # required: one of the 9 patterns
    model: gpt-4o-mini            # default model for all steps
    system_prompt: "..."          # prepended to every step prompt
    depends_on: [other_node]      # wired to pattern entry node
    config:                       # pattern-specific settings
      key: value
    steps:                        # per-step overrides
      step_name:
        model: gpt-4o
        system_prompt: "Override prompt for this step only."
```

## Built-in patterns

### `critic`

Three-step self-improvement: **draft → critique → refine**.

```yaml
pattern: critic
config:
  rounds: 1        # number of draft→critique→refine cycles (default: 1)
steps:
  draft:
    model: gpt-4o-mini
  critique:
    model: gpt-4o
  refine:
    model: gpt-4o-mini
```

Exit node: `<id>.refine`

---

### `debate`

Two agents argue opposing sides, a judge picks the winner: **pro → con → judge**.

```yaml
pattern: debate
config:
  rounds: 1
steps:
  pro:
    system_prompt: "Argue strongly in favour of the proposal."
  con:
    system_prompt: "Argue strongly against the proposal."
  judge:
    model: gpt-4o
```

Exit node: `<id>.judge`

---

### `best_of_n`

Generate N independent candidates, pick the best: **candidate_1..N → selector**.

```yaml
pattern: best_of_n
config:
  n: 3            # number of parallel candidates (default: 3)
steps:
  candidate:
    system_prompt: "Generate one solution."
  selector:
    system_prompt: "Pick the best candidate and explain why."
```

Exit node: `<id>.selector`

---

### `reflexion`

Iterative self-reflection: **act → evaluate → reflect** (loops).

```yaml
pattern: reflexion
config:
  max_iterations: 3
steps:
  act:
    system_prompt: "Attempt to solve the task."
  evaluate:
    system_prompt: "Score the attempt: pass/fail with reasoning."
  reflect:
    system_prompt: "Produce an improved attempt based on evaluation."
```

Exit node: `<id>.reflect`

---

### `scatter`

Fan-out/fan-in: **mapper → worker_1..N (parallel) → reducer**.

```yaml
pattern: scatter
config:
  max_workers: 4    # number of parallel workers (default: 10)
steps:
  mapper:
    system_prompt: "Split input into sub-tasks."
  worker:
    system_prompt: "Process the assigned sub-task."
  reducer:
    system_prompt: "Combine all worker results."
```

Exit node: `<id>.reducer`

---

### `fsm`

Finite state machine: cycles through **state_1..N → terminal** until a terminal state is reached.

```yaml
pattern: fsm
config:
  states: [idle, processing, done]
  terminal: done
steps:
  idle:
    system_prompt: "Check if work is available."
  processing:
    system_prompt: "Process one item."
  done:
    system_prompt: "Summarize completed work."
```

Exit node: `<id>.terminal_state`

---

### `constitutional`

Two-pass content review: **draft → critique (per-principle) → revise**.

```yaml
pattern: constitutional
config:
  principles:
    - "Be factually accurate."
    - "Avoid harmful content."
steps:
  draft:
    system_prompt: "Write a response."
  critique:
    system_prompt: "Evaluate the draft against the stated principle."
  revise:
    system_prompt: "Rewrite the draft addressing all critiques."
```

Exit node: `<id>.revise`

---

### `chain_of_verification`

Draft → verify each claim → synthesize verified output.

```yaml
pattern: chain_of_verification
config:
  num_verifications: 3
steps:
  draft:
    system_prompt: "Draft an answer."
  verify:
    system_prompt: "Identify and verify one key claim."
  synthesize:
    system_prompt: "Produce a final answer using only verified facts."
```

Exit node: `<id>.synthesize`

---

### `plan_execute`

Decompose a task then execute each step: **planner → executor_1..N → aggregator**.

```yaml
pattern: plan_execute
config:
  max_steps: 5
steps:
  planner:
    system_prompt: "Decompose the task into numbered steps."
  executor:
    system_prompt: "Execute the assigned step."
  aggregator:
    system_prompt: "Combine all step outputs into a final result."
```

Exit node: `<id>.aggregator`

---

## Chaining patterns

Pattern nodes can depend on each other. Dependency rewiring is automatic:

```yaml
nodes:
  brainstorm:
    pattern: scatter
    config:
      max_workers: 3

  polish:
    pattern: critic
    depends_on: [brainstorm]   # automatically wired to brainstorm.reducer
```

## Web UI

Open the **Node Palette** in the DAG editor (bottom-left panel) to drag pattern types onto the canvas. Each pattern node renders as a collapsed group. Click **Expand** to see internal steps. Use the sidebar to configure per-step model and prompt overrides.
