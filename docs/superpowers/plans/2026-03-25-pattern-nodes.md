# Pattern Nodes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 9 pattern macro-nodes (Critic, Debate, Best-of-N, Reflexion, Scatter, FSM, Constitutional, Chain-of-Verification, Plan-Execute) that expand into sub-DAGs at YAML parse time, with collapsible UI groups.

**Architecture:** PatternExpander reads `pattern:` fields in YAML, generates real NodeSpec + edges, merges into WorkflowSpec before DAG construction. UI shows collapsed/expanded groups. No new runtime primitives — patterns use existing LLM nodes, edges, and back_edges.

**Tech Stack:** Python 3.11 (Pydantic v2, pytest), React 18 + TypeScript (ReactFlow, Tailwind)

**Spec:** `docs/superpowers/specs/2026-03-25-pattern-nodes-design.md`

---

## File Structure

### New files (Python backend):
- `src/binex/patterns/__init__.py` — exports `expand_patterns()`
- `src/binex/patterns/expander.py` — PatternExpander: reads pattern specs, produces NodeSpecs + edges
- `src/binex/patterns/models.py` — PatternSpec, StepConfig Pydantic models
- `src/binex/patterns/templates/__init__.py` — registry of all pattern templates
- `src/binex/patterns/templates/critic.py` — Critic template
- `src/binex/patterns/templates/debate.py` — Debate template
- `src/binex/patterns/templates/best_of_n.py` — Best-of-N template
- `src/binex/patterns/templates/reflexion.py` — Reflexion template
- `src/binex/patterns/templates/scatter.py` — Scatter template
- `src/binex/patterns/templates/fsm.py` — FSM template
- `src/binex/patterns/templates/constitutional.py` — Constitutional template
- `src/binex/patterns/templates/chain_of_verification.py` — Chain-of-Verification template
- `src/binex/patterns/templates/plan_execute.py` — Plan-Execute template

### New files (tests):
- `tests/unit/test_pattern_models.py` — PatternSpec/StepConfig validation
- `tests/unit/test_pattern_expander.py` — expansion logic for all 9 patterns
- `tests/unit/test_pattern_integration.py` — end-to-end: YAML → expand → DAG → validate
- `examples/patterns/critic.yaml` — example workflow using critic pattern
- `examples/patterns/debate.yaml` — example workflow using debate pattern

### New files (frontend):
- `ui/src/components/dag/PatternGroup.tsx` — collapsible pattern group container
- `ui/src/components/editor/PatternConfig.tsx` — pattern-specific settings panel

### Modified files:
- `src/binex/workflow_spec/loader.py` — call `expand_patterns()` before DAG construction
- `src/binex/models/workflow.py` — add `pattern` field to NodeSpec, add `group` metadata field
- `ui/src/components/editor/NodePalette.tsx` — add 9 pattern entries
- `ui/src/lib/yaml-to-graph.ts` — detect pattern nodes, generate group metadata
- `ui/src/components/editor/EditableNode.tsx` — render PatternConfig for pattern nodes

---

### Task 1: Pattern Models

**Files:**
- Create: `src/binex/patterns/__init__.py`
- Create: `src/binex/patterns/models.py`
- Test: `tests/unit/test_pattern_models.py`

- [ ] **Step 1: Write tests for PatternSpec model**

```python
# tests/unit/test_pattern_models.py
import pytest
from binex.patterns.models import PatternSpec, StepConfig

class TestStepConfig:
    def test_minimal(self):
        s = StepConfig(prompt="Do the thing")
        assert s.prompt == "Do the thing"
        assert s.model is None

    def test_with_model_override(self):
        s = StepConfig(prompt="Draft it", model="llm://claude-haiku-4-5")
        assert s.model == "llm://claude-haiku-4-5"

class TestPatternSpec:
    def test_critic_minimal(self):
        p = PatternSpec(id="researcher", pattern="critic", model="llm://claude-sonnet-4-6")
        assert p.pattern == "critic"
        assert p.config == {}
        assert p.steps == {}

    def test_critic_with_steps(self):
        p = PatternSpec(
            id="researcher",
            pattern="critic",
            model="llm://claude-sonnet-4-6",
            system_prompt="Research X",
            config={"rounds": 2},
            steps={"draft": StepConfig(model="llm://claude-haiku-4-5", prompt="Write draft")},
        )
        assert p.config["rounds"] == 2
        assert p.steps["draft"].model == "llm://claude-haiku-4-5"

    def test_unknown_pattern_rejected(self):
        with pytest.raises(ValueError, match="Unknown pattern"):
            PatternSpec(id="x", pattern="nonexistent", model="llm://m")

    def test_debate_requires_agents_count(self):
        p = PatternSpec(id="d", pattern="debate", model="llm://m", config={"agents": 3})
        assert p.config["agents"] == 3
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `cd /home/jetson/.openclaw/workspace/binex && python -m pytest tests/unit/test_pattern_models.py -v`
Expected: ImportError (module doesn't exist)

- [ ] **Step 3: Implement PatternSpec and StepConfig**

```python
# src/binex/patterns/__init__.py
from binex.patterns.expander import expand_patterns

__all__ = ["expand_patterns"]
```

```python
# src/binex/patterns/models.py
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, field_validator

VALID_PATTERNS = frozenset({
    "critic", "debate", "best_of_n", "reflexion", "scatter",
    "fsm", "constitutional", "chain_of_verification", "plan_execute",
})

class StepConfig(BaseModel):
    prompt: str | None = None
    model: str | None = None

class PatternSpec(BaseModel):
    id: str
    pattern: str
    model: str
    system_prompt: str = ""
    config: dict[str, Any] = {}
    steps: dict[str, StepConfig] = {}
    depends_on: list[str] = []
    inputs: dict[str, Any] = {}
    outputs: list[str] = []
    budget: Any = None

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v: str) -> str:
        if v not in VALID_PATTERNS:
            raise ValueError(f"Unknown pattern: {v}. Valid: {sorted(VALID_PATTERNS)}")
        return v
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `python -m pytest tests/unit/test_pattern_models.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/binex/patterns/ tests/unit/test_pattern_models.py
git commit -m "feat(patterns): add PatternSpec and StepConfig models"
```

---

### Task 2: Pattern Template Interface + Critic Template

**Files:**
- Create: `src/binex/patterns/templates/__init__.py`
- Create: `src/binex/patterns/templates/critic.py`
- Test: `tests/unit/test_pattern_expander.py`

- [ ] **Step 1: Write tests for Critic expansion**

```python
# tests/unit/test_pattern_expander.py
import pytest
from binex.patterns.models import PatternSpec
from binex.patterns.templates.critic import expand_critic

class TestCriticExpansion:
    def test_basic_expansion(self):
        spec = PatternSpec(id="r", pattern="critic", model="llm://claude-sonnet-4-6")
        nodes, edges, back_edges = expand_critic(spec)

        assert len(nodes) == 3
        ids = {n.id for n in nodes}
        assert ids == {"r.draft", "r.critique", "r.refine"}

        # All nodes use the default model
        for n in nodes:
            assert n.agent == "llm://claude-sonnet-4-6"

        # Edges: draft -> critique -> refine
        assert ("r.draft", "r.critique") in edges
        assert ("r.critique", "r.refine") in edges

    def test_step_model_override(self):
        spec = PatternSpec(
            id="r", pattern="critic", model="llm://claude-sonnet-4-6",
            steps={"draft": {"model": "llm://claude-haiku-4-5", "prompt": "Quick draft"}},
        )
        nodes, edges, back_edges = expand_critic(spec)
        draft = next(n for n in nodes if n.id == "r.draft")
        assert draft.agent == "llm://claude-haiku-4-5"
        assert "Quick draft" in draft.system_prompt

    def test_rounds_create_back_edge(self):
        spec = PatternSpec(id="r", pattern="critic", model="llm://m", config={"rounds": 3})
        nodes, edges, back_edges = expand_critic(spec)
        assert len(back_edges) == 1
        be = back_edges[0]
        assert be["node_id"] == "r.refine"
        assert be["target"] == "r.draft"
        assert be["max_iterations"] == 3

    def test_group_metadata(self):
        spec = PatternSpec(id="r", pattern="critic", model="llm://m")
        nodes, _, _ = expand_critic(spec)
        for n in nodes:
            assert n.config.get("_pattern_group") == "r"
            assert n.config.get("_pattern_type") == "critic"

    def test_external_depends_wired_to_entry(self):
        spec = PatternSpec(id="r", pattern="critic", model="llm://m", depends_on=["upstream"])
        nodes, _, _ = expand_critic(spec)
        draft = next(n for n in nodes if n.id == "r.draft")
        assert "upstream" in draft.depends_on
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `python -m pytest tests/unit/test_pattern_expander.py::TestCriticExpansion -v`
Expected: ImportError

- [ ] **Step 3: Implement template interface and Critic template**

```python
# src/binex/patterns/templates/__init__.py
from __future__ import annotations
from typing import TYPE_CHECKING
from binex.patterns.templates.critic import expand_critic

if TYPE_CHECKING:
    from binex.patterns.models import PatternSpec
    from binex.models.workflow import NodeSpec, BackEdge

ExpandResult = tuple[list["NodeSpec"], list[tuple[str, str]], list[dict]]

TEMPLATE_REGISTRY: dict[str, callable] = {
    "critic": expand_critic,
}

def expand_pattern(spec: "PatternSpec") -> ExpandResult:
    """Expand a pattern spec into nodes, edges, and back_edges."""
    fn = TEMPLATE_REGISTRY.get(spec.pattern)
    if fn is None:
        raise ValueError(f"No template for pattern: {spec.pattern}")
    return fn(spec)
```

```python
# src/binex/patterns/templates/critic.py
from __future__ import annotations
from binex.models.workflow import NodeSpec
from binex.patterns.models import PatternSpec

DEFAULT_PROMPTS = {
    "draft": "Based on the input, produce a thorough draft.",
    "critique": "Review the draft. List specific weaknesses, gaps, and errors.",
    "refine": "Revise the draft addressing each critique point.",
}

def expand_critic(spec: PatternSpec):
    """Expand critic pattern into draft → critique → refine nodes."""
    rounds = spec.config.get("rounds", 1)
    nodes = []
    group_meta = {"_pattern_group": spec.id, "_pattern_type": "critic"}

    for step_name in ("draft", "critique", "refine"):
        step_cfg = spec.steps.get(step_name)
        model = (step_cfg.model if step_cfg and step_cfg.model else spec.model)
        prompt_parts = []
        if spec.system_prompt:
            prompt_parts.append(spec.system_prompt)
        step_prompt = step_cfg.prompt if step_cfg and step_cfg.prompt else DEFAULT_PROMPTS[step_name]
        prompt_parts.append(step_prompt)

        node = NodeSpec(
            id=f"{spec.id}.{step_name}",
            agent=model,
            system_prompt="\n\n".join(prompt_parts),
            depends_on=[],
            inputs=spec.inputs if step_name == "draft" else {},
            outputs=spec.outputs if step_name == "refine" else ["result"],
            config={**group_meta},
            budget=spec.budget,
        )
        nodes.append(node)

    # Wire depends_on
    nodes[0].depends_on = list(spec.depends_on)  # draft inherits external deps
    nodes[1].depends_on = [f"{spec.id}.draft"]
    nodes[2].depends_on = [f"{spec.id}.critique"]

    # Edges
    edges = [
        (f"{spec.id}.draft", f"{spec.id}.critique"),
        (f"{spec.id}.critique", f"{spec.id}.refine"),
    ]

    # Back-edge for multiple rounds
    back_edges = []
    if rounds > 1:
        back_edges.append({
            "node_id": f"{spec.id}.refine",
            "target": f"{spec.id}.draft",
            "max_iterations": rounds,
            "when": "true",
        })

    return nodes, edges, back_edges
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `python -m pytest tests/unit/test_pattern_expander.py::TestCriticExpansion -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/binex/patterns/templates/ tests/unit/test_pattern_expander.py
git commit -m "feat(patterns): critic template — draft→critique→refine expansion"
```

---

### Task 3: Remaining 8 Pattern Templates

**Files:**
- Create: `src/binex/patterns/templates/debate.py`
- Create: `src/binex/patterns/templates/best_of_n.py`
- Create: `src/binex/patterns/templates/reflexion.py`
- Create: `src/binex/patterns/templates/scatter.py`
- Create: `src/binex/patterns/templates/fsm.py`
- Create: `src/binex/patterns/templates/constitutional.py`
- Create: `src/binex/patterns/templates/chain_of_verification.py`
- Create: `src/binex/patterns/templates/plan_execute.py`
- Modify: `src/binex/patterns/templates/__init__.py` — register all templates
- Test: `tests/unit/test_pattern_expander.py` — add test classes per template

Each template follows the same interface as Critic: `expand_<name>(spec) -> (nodes, edges, back_edges)`.

- [ ] **Step 1: Implement all 8 templates**

Each template generates nodes + edges per the spec:
- **Debate:** agent_1..agent_N (parallel, no deps between them) → collector → judge. Back-edge judge → agents for rounds > 1.
- **Best-of-N:** variant_1..variant_N (parallel) → judge. No back-edge.
- **Reflexion:** actor → reflector. Back-edge reflector → actor with `when: ${reflector.result} != DONE`, max_iterations from config.
- **Scatter:** mapper → worker_1..worker_N (parallel, depend on mapper) → reducer. N = config.max_workers (default 10). Workers get when-conditions for dynamic activation.
- **FSM:** state nodes per config.states. Back-edges between states with when-conditions matching routing keys.
- **Constitutional:** generate → critique_principles → revise. Single pass, no back-edge.
- **Chain-of-Verification:** generate → extract_claims → verify_each → revise. Single pass.
- **Plan-Execute:** planner → executor → verifier. Back-edge verifier → planner with max_iterations=3.

- [ ] **Step 2: Write tests for each template**

One test class per template in `tests/unit/test_pattern_expander.py`. Each tests:
- Correct node count and IDs
- Correct edge wiring
- Default prompts present
- Model overrides work
- Back-edges present when expected
- Group metadata on all nodes

- [ ] **Step 3: Register all templates in `__init__.py`**

```python
TEMPLATE_REGISTRY: dict[str, callable] = {
    "critic": expand_critic,
    "debate": expand_debate,
    "best_of_n": expand_best_of_n,
    "reflexion": expand_reflexion,
    "scatter": expand_scatter,
    "fsm": expand_fsm,
    "constitutional": expand_constitutional,
    "chain_of_verification": expand_chain_of_verification,
    "plan_execute": expand_plan_execute,
}
```

- [ ] **Step 4: Run all expander tests**

Run: `python -m pytest tests/unit/test_pattern_expander.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/binex/patterns/templates/ tests/unit/test_pattern_expander.py
git commit -m "feat(patterns): all 9 pattern templates implemented"
```

---

### Task 4: PatternExpander + YAML Integration

**Files:**
- Create: `src/binex/patterns/expander.py`
- Modify: `src/binex/models/workflow.py` — add `pattern` field to NodeSpec
- Modify: `src/binex/workflow_spec/loader.py` — call expand_patterns() before DAG
- Test: `tests/unit/test_pattern_integration.py`

- [ ] **Step 1: Write integration tests**

```python
# tests/unit/test_pattern_integration.py
import pytest
from binex.workflow_spec.loader import load_workflow_from_string

CRITIC_YAML = """
name: test-critic
nodes:
  researcher:
    pattern: critic
    model: llm://claude-sonnet-4-6
    system_prompt: "Research AI safety"
    config:
      rounds: 2
  writer:
    agent: llm://claude-sonnet-4-6
    depends_on: [researcher]
    system_prompt: "Write article from research"
"""

class TestPatternYAMLIntegration:
    def test_critic_expands_in_workflow(self):
        spec = load_workflow_from_string(CRITIC_YAML, fmt="yaml")
        # Pattern node replaced by 3 sub-nodes
        assert "researcher" not in spec.nodes
        assert "researcher.draft" in spec.nodes
        assert "researcher.critique" in spec.nodes
        assert "researcher.refine" in spec.nodes
        # Writer depends on exit node
        assert "researcher.refine" in spec.nodes["writer"].depends_on

    def test_dag_builds_after_expansion(self):
        from binex.graph.dag import DAG
        spec = load_workflow_from_string(CRITIC_YAML, fmt="yaml")
        dag = DAG.from_workflow(spec)
        order = dag.topological_order()
        assert order.index("researcher.draft") < order.index("researcher.critique")
        assert order.index("researcher.critique") < order.index("researcher.refine")
        assert order.index("researcher.refine") < order.index("writer")
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `python -m pytest tests/unit/test_pattern_integration.py -v`
Expected: FAIL (pattern: key not recognized)

- [ ] **Step 3: Add `pattern` field to NodeSpec**

Modify `src/binex/models/workflow.py` — add to NodeSpec class:
```python
pattern: str | None = None
```

- [ ] **Step 4: Implement PatternExpander**

```python
# src/binex/patterns/expander.py
from __future__ import annotations
from binex.models.workflow import WorkflowSpec, NodeSpec
from binex.patterns.models import PatternSpec, StepConfig
from binex.patterns.templates import expand_pattern

def expand_patterns(spec: WorkflowSpec) -> WorkflowSpec:
    """Find pattern nodes in spec, expand them into sub-DAG nodes."""
    expanded_nodes: dict[str, NodeSpec] = {}
    extra_edges: list[tuple[str, str]] = []
    pattern_exits: dict[str, str] = {}  # pattern_id -> exit_node_id
    pattern_entries: dict[str, str] = {}  # pattern_id -> entry_node_id

    # Separate pattern nodes from regular nodes
    regular_nodes: dict[str, NodeSpec] = {}
    for node_id, node in spec.nodes.items():
        if node.pattern:
            pspec = PatternSpec(
                id=node_id,
                pattern=node.pattern,
                model=node.agent or node.config.get("model", ""),
                system_prompt=node.system_prompt or "",
                config={k: v for k, v in (node.config or {}).items() if not k.startswith("_")},
                steps={k: StepConfig(**v) if isinstance(v, dict) else v
                       for k, v in node.config.get("steps", {}).items()},
                depends_on=node.depends_on or [],
                inputs=node.inputs or {},
                outputs=node.outputs or [],
                budget=node.budget,
            )
            nodes, edges, back_edges = expand_pattern(pspec)
            for n in nodes:
                expanded_nodes[n.id] = n
            extra_edges.extend(edges)

            # Track entry/exit for rewiring
            pattern_entries[node_id] = nodes[0].id
            pattern_exits[node_id] = nodes[-1].id

            # Apply back_edges to expanded nodes
            for be in back_edges:
                target_node = expanded_nodes[be["node_id"]]
                from binex.models.workflow import BackEdge
                target_node.back_edge = BackEdge(
                    target=be["target"],
                    when=be.get("when", "true"),
                    max_iterations=be.get("max_iterations", 5),
                )
        else:
            regular_nodes[node_id] = node

    if not expanded_nodes:
        return spec  # No patterns, return unchanged

    # Rewire depends_on: any node depending on a pattern ID -> depend on exit node
    for node_id, node in regular_nodes.items():
        node.depends_on = [
            pattern_exits.get(dep, dep) for dep in (node.depends_on or [])
        ]

    # Merge all nodes
    all_nodes = {**regular_nodes, **expanded_nodes}

    # Apply extra edges as depends_on
    for src, tgt in extra_edges:
        if tgt in all_nodes and src not in (all_nodes[tgt].depends_on or []):
            if all_nodes[tgt].depends_on is None:
                all_nodes[tgt].depends_on = []
            all_nodes[tgt].depends_on.append(src)

    return WorkflowSpec(
        version=spec.version,
        name=spec.name,
        description=spec.description,
        nodes=all_nodes,
        defaults=spec.defaults,
        budget=spec.budget,
        webhook=spec.webhook,
        mcp_servers=spec.mcp_servers,
        schedule=spec.schedule,
        source_path=spec.source_path,
    )
```

- [ ] **Step 5: Wire into YAML loader**

Modify `src/binex/workflow_spec/loader.py` — in `load_workflow_from_string()`, after constructing WorkflowSpec and before returning:

```python
from binex.patterns import expand_patterns
spec = expand_patterns(spec)
```

- [ ] **Step 6: Run integration tests**

Run: `python -m pytest tests/unit/test_pattern_integration.py -v`
Expected: All pass

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/unit/ -v`
Expected: All existing tests still pass

- [ ] **Step 8: Commit**

```bash
git add src/binex/patterns/expander.py src/binex/models/workflow.py src/binex/workflow_spec/loader.py tests/unit/test_pattern_integration.py
git commit -m "feat(patterns): PatternExpander + YAML integration — patterns expand into sub-DAGs"
```

---

### Task 5: Example YAML Workflows

**Files:**
- Create: `examples/patterns/critic.yaml`
- Create: `examples/patterns/debate.yaml`

- [ ] **Step 1: Write example critic workflow**

```yaml
# examples/patterns/critic.yaml
name: research-with-critic
description: Research a topic using the Critic pattern for iterative refinement
nodes:
  researcher:
    pattern: critic
    model: llm://claude-sonnet-4-6
    system_prompt: "You are an AI safety researcher."
    config:
      rounds: 2
      steps:
        draft:
          model: llm://claude-haiku-4-5
          prompt: "Write a research summary on the given topic"
        critique:
          prompt: "Identify factual errors, logical gaps, and missing perspectives"
        refine:
          prompt: "Produce a final version addressing all critique points"
    outputs: [report]

  publisher:
    agent: llm://claude-sonnet-4-6
    depends_on: [researcher]
    system_prompt: "Format the research report for publication"
    outputs: [article]
```

- [ ] **Step 2: Write example debate workflow**

```yaml
# examples/patterns/debate.yaml
name: policy-debate
description: Three AI agents debate a policy question, judge synthesizes
nodes:
  debaters:
    pattern: debate
    model: llm://claude-sonnet-4-6
    system_prompt: "Debate the given policy question"
    config:
      agents: 3
      rounds: 2
    outputs: [verdict]
```

- [ ] **Step 3: Verify examples load and expand**

Run: `python -c "from binex.workflow_spec import load_workflow; s=load_workflow('examples/patterns/critic.yaml'); print([n for n in s.nodes])"`
Expected: `['researcher.draft', 'researcher.critique', 'researcher.refine', 'publisher']`

- [ ] **Step 4: Commit**

```bash
git add examples/patterns/
git commit -m "docs(patterns): example workflows for critic and debate patterns"
```

---

### Task 6: Frontend — Pattern Palette

**Files:**
- Modify: `ui/src/components/editor/NodePalette.tsx`

- [ ] **Step 1: Add pattern node types to NODE_TYPES**

Add a new `PATTERN_TYPES` array with 9 entries, category `'PATTERNS'`:
- critic: label "Critic", icon Repeat, color '#ec4899'
- debate: label "Debate", icon Users, color '#ec4899'
- best_of_n: label "Best of N", icon Trophy, color '#ec4899'
- reflexion: label "Reflexion", icon RefreshCw, color '#ec4899'
- scatter: label "Scatter", icon GitBranch, color '#ec4899'
- fsm: label "State Machine", icon Workflow, color '#ec4899'
- constitutional: label "Constitutional", icon Scale, color '#ec4899'
- chain_of_verification: label "Verify Chain", icon CheckCheck, color '#ec4899'
- plan_execute: label "Plan & Execute", icon ListChecks, color '#ec4899'

Each uses `agentPrefix: 'pattern://'` and `defaultAgent: 'pattern://<name>'`.

Add a "Patterns" section in the palette UI below existing categories.

- [ ] **Step 2: Verify palette renders**

Run dev server, check that 9 new pattern items appear in the sidebar palette.

- [ ] **Step 3: Commit**

```bash
git add ui/src/components/editor/NodePalette.tsx
git commit -m "feat(ui): add 9 pattern types to node palette"
```

---

### Task 7: Frontend — Pattern Group (Collapse/Expand)

**Files:**
- Create: `ui/src/components/dag/PatternGroup.tsx`
- Modify: `ui/src/lib/yaml-to-graph.ts` — detect `_pattern_group` metadata
- Modify: `ui/src/components/dag/CustomNode.tsx` — render group container

- [ ] **Step 1: Create PatternGroup component**

A React component that:
- Receives group ID, pattern type, and child node IDs
- Renders a dashed-border container around child nodes
- Has a header with pattern icon + name + collapse/expand toggle
- When collapsed: hides children, shows single compact node with input/output handles
- When expanded: shows children inside container

- [ ] **Step 2: Update yaml-to-graph.ts**

In `parseWorkflowYaml()`, detect nodes with `config._pattern_group`. Group them by group ID. Generate `PatternGroup` metadata alongside regular nodes.

- [ ] **Step 3: Update CustomNode.tsx**

When rendering a node that belongs to a pattern group, wrap it in PatternGroup context. Handle collapse state.

- [ ] **Step 4: Verify in browser**

Load critic.yaml example. Verify:
- Pattern appears as collapsed group initially
- Click expand → shows draft, critique, refine nodes inside container
- Click collapse → back to single block
- Edges from upstream/downstream connect to group boundary

- [ ] **Step 5: Commit**

```bash
git add ui/src/components/dag/PatternGroup.tsx ui/src/lib/yaml-to-graph.ts ui/src/components/dag/CustomNode.tsx
git commit -m "feat(ui): collapsible pattern group in DAG editor"
```

---

### Task 8: Frontend — Pattern Config Panel

**Files:**
- Create: `ui/src/components/editor/PatternConfig.tsx`
- Modify: `ui/src/components/editor/EditableNode.tsx`

- [ ] **Step 1: Create PatternConfig component**

Panel that shows when a collapsed pattern node is selected:
- Pattern type (read-only badge)
- Default model dropdown
- Pattern-specific config (rounds input for critic, agents count for debate, etc.)
- Per-step section: expandable accordion, each step has model dropdown + prompt textarea
- "Expand to Sub-graph" button (converts pattern to individual nodes, one-way)

- [ ] **Step 2: Wire into EditableNode**

In `EditableNode.tsx`, detect `nodeType === 'pattern'` and render `<PatternConfig>` instead of standard LLM config.

- [ ] **Step 3: Verify in browser**

Click a collapsed pattern node. Verify config panel shows pattern-specific settings.

- [ ] **Step 4: Commit**

```bash
git add ui/src/components/editor/PatternConfig.tsx ui/src/components/editor/EditableNode.tsx
git commit -m "feat(ui): pattern config panel with per-step overrides"
```

---

### Task 9: Final Integration + Full Test Suite

**Files:**
- Modify: various (fixes from integration testing)

- [ ] **Step 1: Run full backend test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All pass including new pattern tests

- [ ] **Step 2: Run ruff + mypy**

Run: `ruff check src/binex/patterns/` and `mypy src/binex/patterns/`
Expected: 0 errors

- [ ] **Step 3: Run TypeScript checks**

Run: `cd ui && npx tsc --noEmit`
Expected: 0 errors

- [ ] **Step 4: Test end-to-end: load critic.yaml → execute → verify artifacts**

Run a critic workflow locally and verify:
- 3 LLM calls happen (draft, critique, refine)
- Cost tracking shows per-step costs
- Trace shows 3 spans grouped under pattern
- Output artifact from refine step is accessible

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(patterns): complete pattern nodes — 9 patterns, UI groups, config panel"
```
