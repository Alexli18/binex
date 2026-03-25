# Pattern Nodes — Design Spec

## Problem

Binex has the primitives (LLM nodes, edges, back_edges) to build multi-agent patterns like Critic, Debate, and Reflexion — but users must wire them manually every time. This takes 10+ nodes and careful prompt engineering for each pattern. Competing tools (Tama) offer these as one-click constructs.

## Solution

Pattern Nodes are macro-nodes that expand into sub-DAGs of real LLM nodes at YAML parse time. In the UI, they display as collapsible groups. The runtime sees only standard nodes — no new execution primitives needed.

## YAML Format

```yaml
researcher:
  pattern: critic
  model: llm://claude-sonnet-4-6
  system_prompt: "Research topic X"
  config:
    rounds: 2
    steps:
      draft:
        model: llm://claude-haiku-4-5
        prompt: "Write first draft"
      critique:
        prompt: "Find weak points"
      refine:
        model: llm://claude-sonnet-4-6
        prompt: "Fix based on critique"
```

- `pattern:` replaces `agent:` — signals this is a macro-node
- `model:` — default model for all steps (overridable per-step)
- `system_prompt:` — injected into all steps as context
- `config.steps:` — optional per-step overrides (model, prompt)
- `config.rounds:` — iteration count for patterns that loop (critic, debate)
- Without `steps:`, default prompts are generated from the pattern template

## Architecture

### Components

1. **PatternExpander** (`src/binex/patterns/expander.py`) — reads pattern spec, produces `list[NodeSpec]` + edges + back_edges
2. **Pattern Templates** (`src/binex/patterns/templates/`) — one module per pattern, defines nodes/edges/default prompts
3. **YAML Parser Update** (`src/binex/workflow_spec/`) — detect `pattern:` key, route to PatternExpander before DAG construction
4. **UI PatternGroup** (`ui/src/components/dag/PatternGroup.tsx`) — collapsible container in DAG editor
5. **UI PatternPalette** (`ui/src/components/editor/NodePalette.tsx`) — 9 patterns in drag-and-drop palette
6. **UI PatternConfig** (`ui/src/components/editor/PatternConfig.tsx`) — settings panel: model per step, prompts, iterations

### Data Flow

```
YAML input
  → parse_workflow_spec()
  → detect pattern: nodes
  → PatternExpander.expand(pattern_spec) → list[NodeSpec] + edges
  → merge expanded nodes into WorkflowSpec (prefixed: {node_id}.draft, {node_id}.critique, etc.)
  → DAG.from_workflow() (standard path)
  → Scheduler → Dispatcher → LLM adapters (standard execution)
```

### Node ID Convention

Expanded nodes are prefixed with the pattern node's ID:
- Pattern node `researcher` with pattern `critic` expands to:
  - `researcher.draft`
  - `researcher.critique`
  - `researcher.refine`
- External edges targeting `researcher` are rewired to the pattern's entry node
- External edges from `researcher` are rewired from the pattern's exit node

### Sub-DAG Group Metadata

Each expanded node carries `group: {id: "researcher", pattern: "critic", collapsed: true}` in its metadata. The UI uses this to render collapsible groups.

## 9 Pattern Templates

### 1. Critic
**Nodes:** draft → critique → refine
**Back-edge:** refine → draft (when rounds > 1, max_iterations = rounds)
**Default prompts:**
- draft: "Based on the input, produce a thorough draft."
- critique: "Review the draft. List specific weaknesses, gaps, and errors."
- refine: "Revise the draft addressing each critique point."

### 2. Debate
**Nodes:** agent_1..agent_N (parallel) → collector → judge
**Back-edge:** judge → agent_1..agent_N (for multi-round: each round agents see previous transcripts)
**Config:** `agents: int` (default 3), `rounds: int` (default 2)
**Default prompts:**
- agents: "Argue your position on the topic. Consider and address other perspectives."
- judge: "Evaluate all arguments. Synthesize the strongest position with reasoning."

### 3. Best-of-N
**Nodes:** variant_1..variant_N (parallel) → judge
**No back-edge** (single round)
**Config:** `n: int` (default 3)
**Default prompts:**
- variants: "Generate a solution to the given task." (temperature varied per variant)
- judge: "Compare all variants. Select the best one and explain why."

### 4. Reflexion
**Nodes:** actor → reflector
**Back-edge:** reflector → actor (when output does not start with "DONE:", max_iterations configurable)
**Default prompts:**
- actor: "Execute the task. Use available tools if needed."
- reflector: "Evaluate the result. If satisfactory, respond starting with 'DONE:' followed by the final answer. Otherwise, provide specific feedback for improvement."

### 5. Scatter
**Nodes:** mapper → worker_template (dynamic fan-out) → reducer
**Config:** `max_workers: int` (default 10)
**Execution:** Mapper outputs JSON array. PatternExpander creates worker nodes at expansion time with max_workers. At runtime, mapper output determines how many actually execute (rest are skipped via when-conditions).
**Default prompts:**
- mapper: "Break the task into independent subtasks. Output a JSON array of subtask descriptions."
- worker: "Complete the assigned subtask."
- reducer: "Synthesize all worker results into a coherent final output."

### 6. FSM (Finite State Machine)
**Nodes:** state_1..state_N
**Back-edges:** between states, with when-conditions based on output routing keys
**Config:** `states: dict` mapping state names to transitions
```yaml
config:
  initial: research
  states:
    research:
      transitions: {needs_data: research, ready: write}
    write:
      transitions: {needs_revision: research, done: null}
```
**Default prompts:** Per-state, user-defined. Each state agent ends output with `ROUTE: <key>`.

### 7. Constitutional
**Nodes:** generate → critique_principles → revise
**No back-edge** (single pass)
**Config:** `principles: list[str]` (constitutional principles)
**Default prompts:**
- generate: "Produce a response to the input."
- critique_principles: "Evaluate the response against these principles: {principles}. Identify any violations."
- revise: "Revise the response to satisfy all constitutional principles."

### 8. Chain-of-Verification
**Nodes:** generate → extract_claims → verify_each → revise
**No back-edge** (single pass)
**Default prompts:**
- generate: "Answer the question thoroughly."
- extract_claims: "List each factual claim made in the response as a numbered list."
- verify_each: "For each claim, determine if it is correct, incorrect, or uncertain. Provide evidence."
- revise: "Rewrite the original response, correcting any claims marked incorrect or uncertain."

### 9. Plan-Execute
**Nodes:** planner → executor → verifier
**Back-edge:** verifier → planner (when verification fails, max_iterations = 3)
**Config:** `max_steps: int` (default 10)
**Default prompts:**
- planner: "Create a step-by-step plan as a JSON array. Each step: {description, expected_output}."
- executor: "Execute each step in the plan sequentially. Report results for each."
- verifier: "Verify all steps completed successfully. If issues found, respond with 'REPLAN:' and describe what needs to change. If all good, respond with 'DONE:' and the final result."

## UI Design

### Pattern Palette
New category "Patterns" in NodePalette with 9 entries. Each has distinct icon and color. Drag-and-drop creates a collapsed pattern group in the canvas.

### Collapsed View
Single rounded rectangle with:
- Pattern icon + name (e.g., "Critic")
- Model badge
- Expand/collapse toggle
- Input/output handles (connected to entry/exit nodes of sub-DAG)

### Expanded View
Sub-DAG nodes visible inside a dashed-border container. Each inner node is a standard EditableNode. Container header shows pattern name + collapse button.

### Pattern Config Panel
When clicking a collapsed pattern node:
- Pattern type (read-only)
- Default model (dropdown)
- Pattern-specific config (rounds, n, states)
- Per-step section: expandable list of steps, each with model override + prompt textarea
- "Expand to sub-graph" button — permanently converts pattern to individual nodes (one-way, for full customization)

## Integration with Existing Systems

### Cost Tracking
Each expanded sub-node is a real LLM node → cost tracking works automatically per-step. Pattern-level cost = sum of step costs.

### Replay
Each step is replayable individually. Users can replay just the "critique" step of a Critic pattern.

### Budget
Budget applies to the pattern node ID. PatternExpander distributes budget proportionally across steps, or user sets per-step budgets in config.

### Trace
Each step generates its own trace span. Steps are grouped under the pattern node's span ID for hierarchical visualization.

### Back-edges
Patterns that loop (Critic, Reflexion, FSM, Plan-Execute, Debate) use standard `back_edge` with `when` conditions and `max_iterations`. No new runtime primitives.

## Success Criteria

1. All 9 patterns expand correctly into valid sub-DAGs
2. Expanded sub-DAGs execute identically to manually wired equivalents
3. UI collapse/expand works smoothly
4. Drag-and-drop from palette creates correctly configured patterns
5. Per-step model and prompt overrides work
6. Cost, trace, replay, budget — all work transparently on pattern sub-nodes
7. "Expand to sub-graph" permanently converts pattern to editable nodes
