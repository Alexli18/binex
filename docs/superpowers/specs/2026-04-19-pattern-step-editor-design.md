# Pattern Step Editor — Design Spec

**Date:** 2026-04-19  
**Branch:** design/amber-redesign  
**Status:** Approved

## Problem

Pattern nodes (critic, debate, best_of_n, reflexion, scatter, fsm, constitutional, chain_of_verification, plan_execute) currently expose only numeric config fields (rounds, agents, variants, max_iterations) in the visual editor. Per-step model and prompt overrides must be edited in raw YAML. This creates friction for users who want to assign different models or prompts to each step of a pattern.

## Goal

Allow full per-step configuration — model selection and system prompt — directly inside the pattern node in the visual editor, with no need to touch YAML.

## Architecture

### New Component: `PatternStepEditor`

File: `ui/src/components/editor/PatternStepEditor.tsx`

A single collapsible step row inside a pattern node.

**Props:**
```ts
interface PatternStepEditorProps {
  stepKey: string;           // e.g. "draft", "agent_1"
  label: string;             // Display name, e.g. "Draft"
  model: string;             // Current model override ("" = inherit)
  prompt: string;            // Current prompt override
  defaultModel: string;      // Global default model for "inherit" display
  onChange: (model: string, prompt: string) => void;
}
```

**Collapsed state:** shows step label + current model (or "inherit" if empty).  
**Expanded state:** ModelSelect with a first option `[inherit from default]` (value `""`), plus a prompt textarea.

### Updated Component: `PatternConfig`

File: `ui/src/components/editor/PatternConfig.tsx`

Composes per-step editors and manages step list generation.

**Step registry** — `PATTERN_STEPS` — maps each pattern type to its step roles:

| Pattern | Static steps | Dynamic steps |
|---------|-------------|---------------|
| critic | draft, critique, refine | — |
| debate | collector, judge | agent_1..agent_N (from `config.agents`) |
| best_of_n | judge | variant_1..variant_N (from `config.variants`) |
| reflexion | actor, reflector | — |
| scatter | mapper, reducer | — (worker_N are internal, not user-configurable) |
| fsm | — | states from `config.states: string[]` |
| constitutional | generate, critique_principles, revise | — |
| chain_of_verification | generate, extract_claims, verify_each, revise | — |
| plan_execute | planner, executor, verifier | — |

**Layout inside the node (three CollapsibleSections):**
1. **Config** — existing numeric fields (rounds, agents, variants, max_iterations, states)
2. **Model** — single ModelSelect for global default, stored in `config.model`
3. **Steps** — N × PatternStepEditor, badge showing count

### Data Shape in `data.config`

```ts
{
  // Existing numeric fields
  rounds?: number;
  agents?: number;
  variants?: number;
  max_iterations?: number;
  states?: string[];         // FSM only

  // New fields
  model?: string;            // Global default model URI
  steps?: {
    [stepKey: string]: {
      model?: string;        // "" or undefined = inherit
      prompt?: string;       // "" or undefined = no override
    };
  };
}
```

## YAML Serialization

Changes to `graphToYaml` in `WorkflowEditor.tsx`:

For a pattern node, serialize:
```yaml
node_id:
  pattern: critic
  model: llm://openrouter/google/gemma-3-27b-it:free   # omit if empty
  config:
    rounds: 2
  steps:                      # omit entire block if all steps are empty
    draft:
      prompt: "Write a detailed analysis..."           # omit if empty
    critique:
      model: llm://anthropic/claude-haiku-4-5          # omit if empty
      prompt: "Review critically and find flaws..."    # omit if empty
  depends_on: [...]
```

**Serialization rules:**
- `model:` key omitted if `config.model` is empty
- `steps:` block omitted if all steps have empty model and prompt
- Within a step: `model` key omitted if empty, `prompt` key omitted if empty
- Empty step objects (`{}`) omitted entirely

## YAML Deserialization

`yamlToRfGraph` already reads arbitrary fields into `data.config`. Pattern nodes need to additionally parse `model` and `steps` from the YAML node into `data.config.model` and `data.config.steps`.

This requires a small update to the pattern node parsing section of `yamlToRfGraph`.

## UI Details

**Node width:** 280px (slightly wider than current 260px to fit ModelSelect in step rows).

**ModelSelect "inherit" option:** prepend a special item `{ value: "", label: "[default model]" }` to the model list in step editor context.

**FSM special case:** `config.states` is an editable comma-separated text input (e.g. `plan,research,write,review`), parsed into a string array. Changing the value regenerates the step list.

**Collapsed step display:** show model label (truncated, max 16 chars) or "inherit" in muted text.

**Step count badge:** header of the Steps section shows count, e.g. `Steps (3)`.

## Files Changed

| File | Change |
|------|--------|
| `ui/src/components/editor/PatternStepEditor.tsx` | New component |
| `ui/src/components/editor/PatternConfig.tsx` | Add PATTERN_STEPS registry, render step editors, add Model section |
| `ui/src/pages/WorkflowEditor.tsx` | Update graphToYaml and yamlToRfGraph for pattern model/steps |

## Out of Scope

- Worker steps in Scatter (worker_1..N are internal parallelism, not user-configurable)
- Adding/removing steps beyond what count fields control
- Drag-to-reorder steps
- Pattern validation (wrong model for a step) — handled at run time by the backend
