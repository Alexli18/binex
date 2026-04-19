# Pattern Step Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-step model and system-prompt overrides to pattern nodes in the visual editor, replacing the current placeholder "Configure in YAML" message.

**Architecture:** New `PatternStepEditor` component (collapsed/expanded step row) composed inside an updated `PatternConfig` that adds a PATTERN_STEPS registry, a global Model section, and a Steps section. YAML serialization (`graph-to-yaml.ts`) and deserialization (`WorkflowEditor.tsx:yamlToRfGraph`) updated to emit and parse `model`/`steps` fields. Small `inheritOption` prop added to `ModelSelect` for the inherit-from-default first row.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, js-yaml, ReactFlow

---

## File Map

| File | Action |
|------|--------|
| `ui/src/components/editor/ModelSelect.tsx` | Modify — add `inheritOption` prop |
| `ui/src/components/editor/PatternStepEditor.tsx` | Create — new collapsible step row |
| `ui/src/components/editor/PatternConfig.tsx` | Modify — PATTERN_STEPS registry, Model section, Steps section, FSM states |
| `ui/src/lib/graph-to-yaml.ts` | Modify — serialize pattern node `model` + `steps` |
| `ui/src/pages/WorkflowEditor.tsx` | Modify — update `ParsedYamlWorkflow` type + `yamlToRfGraph` |
| `ui/src/components/editor/EditableNode.tsx` | Modify — expand pattern node to 280px |

---

### Task 1: Add `inheritOption` prop to `ModelSelect`

**Files:**
- Modify: `ui/src/components/editor/ModelSelect.tsx`

- [ ] **Step 1: Add prop to interface and update trigger display**

In `ui/src/components/editor/ModelSelect.tsx`, find `interface ModelSelectProps` (line ~124) and add `inheritOption?: boolean`:

```ts
interface ModelSelectProps {
  value: string;
  onChange: (model: string) => void;
  inheritOption?: boolean;
}
```

Update `export function ModelSelect({ value, onChange }: ModelSelectProps)` at line ~142 to:

```ts
export function ModelSelect({ value, onChange, inheritOption }: ModelSelectProps) {
```

Find this line (~260):
```ts
const displayName = shortName(value) || 'Select model...';
```
Replace with:
```ts
const displayName = (inheritOption && !value) ? '[default model]' : (shortName(value) || 'Select model...');
```

- [ ] **Step 2: Add inherit row at top of dropdown list**

In the dropdown `<div ref={listRef} ...>` block (starts around line 298), insert immediately after the opening `<div ref={listRef} ...>` tag, before the `{/* Recently Used */}` comment:

```tsx
{/* Inherit option */}
{inheritOption && (
  <div>
    <div
      className={`flex items-center gap-2 px-2 py-1.5 text-xs cursor-pointer transition-colors border-b border-[#252528] ${
        value === '' ? 'text-amber-400 bg-amber-500/10' : 'text-[#4a4a52] italic hover:bg-[#252528] hover:text-[#80808a]'
      }`}
      onClick={() => { onChange(''); setOpen(false); }}
    >
      [default model]
    </div>
  </div>
)}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /home/jetson/.openclaw/workspace/binex/.worktrees/design/amber-redesign/ui
npx tsc --noEmit 2>&1 | head -30
```

Expected: zero errors from ModelSelect.tsx

- [ ] **Step 4: Commit**

```bash
cd /home/jetson/.openclaw/workspace/binex/.worktrees/design/amber-redesign
git add ui/src/components/editor/ModelSelect.tsx
git commit -m "feat(editor): add inheritOption prop to ModelSelect"
```

---

### Task 2: Create `PatternStepEditor` component

**Files:**
- Create: `ui/src/components/editor/PatternStepEditor.tsx`

- [ ] **Step 1: Write the component**

```tsx
import { useState } from 'react';
import { ChevronRight, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ModelSelect } from './ModelSelect';

export interface PatternStepEditorProps {
  stepKey: string;
  label: string;
  model: string;
  prompt: string;
  onChange: (model: string, prompt: string) => void;
}

export function PatternStepEditor({ stepKey: _stepKey, label, model, prompt, onChange }: PatternStepEditorProps) {
  const [open, setOpen] = useState(false);

  const modelDisplay = model
    ? (model.split('/').pop() ?? model).slice(0, 16)
    : 'inherit';

  return (
    <div className="border border-[#252528] rounded text-[11px]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 w-full px-2 py-1 hover:bg-[#1a1a1d]/50 transition-colors"
      >
        <ChevronRight
          size={10}
          className={cn('transition-transform duration-150 shrink-0 text-[#4a4a52]', open && 'rotate-90')}
        />
        <span className="text-[#80808a] font-medium truncate">{label}</span>
        <span
          className={cn(
            'ml-auto text-[10px] shrink-0',
            model ? 'text-[#80808a]' : 'text-[#4a4a52] italic',
          )}
        >
          {modelDisplay}
        </span>
      </button>

      {open && (
        <div className="px-2 pb-2 space-y-1.5 border-t border-[#252528]">
          <div className="pt-1.5">
            <div className="flex items-center justify-between mb-0.5">
              <label className="text-[10px] text-[#4a4a52]">Model</label>
              {model && (
                <button
                  type="button"
                  title="Inherit from default"
                  onClick={() => onChange('', prompt)}
                  className="text-[#4a4a52] hover:text-[#80808a] transition-colors"
                >
                  <X size={10} />
                </button>
              )}
            </div>
            <ModelSelect
              value={model}
              onChange={(v) => onChange(v, prompt)}
              inheritOption
            />
          </div>
          <div>
            <label className="block text-[10px] text-[#4a4a52] mb-0.5">Prompt override</label>
            <textarea
              value={prompt}
              onChange={(e) => onChange(model, e.target.value)}
              placeholder="Leave empty to use node-level prompt..."
              rows={3}
              className="w-full bg-[#0b0b0c] border border-[#252528] rounded px-1.5 py-1 text-[#80808a] resize-none text-[10px] focus:outline-none focus:border-[#e8a020]/50 placeholder:text-[#333338]"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/jetson/.openclaw/workspace/binex/.worktrees/design/amber-redesign/ui
npx tsc --noEmit 2>&1 | head -30
```

Expected: zero errors

- [ ] **Step 3: Commit**

```bash
cd /home/jetson/.openclaw/workspace/binex/.worktrees/design/amber-redesign
git add ui/src/components/editor/PatternStepEditor.tsx
git commit -m "feat(editor): add PatternStepEditor component"
```

---

### Task 3: Update `PatternConfig` with PATTERN_STEPS registry, Model section, and Steps section

**Files:**
- Modify: `ui/src/components/editor/PatternConfig.tsx`

- [ ] **Step 1: Rewrite the file**

Replace the entire content of `ui/src/components/editor/PatternConfig.tsx` with:

```tsx
import { useMemo } from 'react';
import { CollapsibleSection } from './CollapsibleSection';
import { ModelSelect } from './ModelSelect';
import { PatternStepEditor } from './PatternStepEditor';

// ---------------------------------------------------------------------------
// Step registry
// ---------------------------------------------------------------------------

interface StepDef {
  key: string;
  label: string;
}

type DynamicSource = 'agents' | 'variants' | 'states';

interface PatternDef {
  label: string;
  fields: Array<{ key: string; label: string; type: 'number' | 'text'; default: number | string }>;
  staticSteps: StepDef[];
  dynamicSteps?: { source: DynamicSource; prefix: string; labelPrefix: string };
}

const PATTERN_CONFIG: Record<string, PatternDef> = {
  critic: {
    label: 'Critic',
    fields: [{ key: 'rounds', label: 'Rounds', type: 'number', default: 1 }],
    staticSteps: [
      { key: 'draft', label: 'Draft' },
      { key: 'critique', label: 'Critique' },
      { key: 'refine', label: 'Refine' },
    ],
  },
  debate: {
    label: 'Debate',
    fields: [
      { key: 'agents', label: 'Agents', type: 'number', default: 2 },
      { key: 'rounds', label: 'Rounds', type: 'number', default: 1 },
    ],
    staticSteps: [
      { key: 'collector', label: 'Collector' },
      { key: 'judge', label: 'Judge' },
    ],
    dynamicSteps: { source: 'agents', prefix: 'agent_', labelPrefix: 'Agent ' },
  },
  best_of_n: {
    label: 'Best of N',
    fields: [{ key: 'variants', label: 'Variants', type: 'number', default: 3 }],
    staticSteps: [{ key: 'judge', label: 'Judge' }],
    dynamicSteps: { source: 'variants', prefix: 'variant_', labelPrefix: 'Variant ' },
  },
  reflexion: {
    label: 'Reflexion',
    fields: [{ key: 'max_iterations', label: 'Max Iterations', type: 'number', default: 3 }],
    staticSteps: [
      { key: 'actor', label: 'Actor' },
      { key: 'reflector', label: 'Reflector' },
    ],
  },
  scatter: {
    label: 'Scatter',
    fields: [{ key: 'max_workers', label: 'Max Workers', type: 'number', default: 10 }],
    staticSteps: [
      { key: 'mapper', label: 'Mapper' },
      { key: 'reducer', label: 'Reducer' },
    ],
  },
  fsm: {
    label: 'State Machine',
    fields: [{ key: 'max_iterations', label: 'Max Iterations', type: 'number', default: 10 }],
    staticSteps: [],
    dynamicSteps: { source: 'states', prefix: '', labelPrefix: '' },
  },
  constitutional: {
    label: 'Constitutional',
    fields: [],
    staticSteps: [
      { key: 'generate', label: 'Generate' },
      { key: 'critique_principles', label: 'Critique Principles' },
      { key: 'revise', label: 'Revise' },
    ],
  },
  chain_of_verification: {
    label: 'Verify Chain',
    fields: [],
    staticSteps: [
      { key: 'generate', label: 'Generate' },
      { key: 'extract_claims', label: 'Extract Claims' },
      { key: 'verify_each', label: 'Verify Each' },
      { key: 'revise', label: 'Revise' },
    ],
  },
  plan_execute: {
    label: 'Plan & Execute',
    fields: [{ key: 'max_iterations', label: 'Max Iterations', type: 'number', default: 3 }],
    staticSteps: [
      { key: 'planner', label: 'Planner' },
      { key: 'executor', label: 'Executor' },
      { key: 'verifier', label: 'Verifier' },
    ],
  },
};

// ---------------------------------------------------------------------------
// Step list builder
// ---------------------------------------------------------------------------

function buildSteps(def: PatternDef, config: Record<string, unknown>): StepDef[] {
  const steps: StepDef[] = [...def.staticSteps];

  if (!def.dynamicSteps) return steps;

  const { source, prefix, labelPrefix } = def.dynamicSteps;

  if (source === 'states') {
    const raw = (config.states as string | undefined) ?? '';
    const names = raw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    for (const name of names) {
      steps.push({ key: name, label: name });
    }
    return steps;
  }

  const count = Number(config[source] ?? (source === 'variants' ? 3 : 2));
  for (let i = 1; i <= count; i++) {
    steps.push({ key: `${prefix}${i}`, label: `${labelPrefix}${i}` });
  }
  return steps;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface StepConfig {
  model?: string;
  prompt?: string;
}

interface PatternConfigProps {
  patternType: string;
  config: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
}

export function PatternConfig({ patternType, config, onChange }: PatternConfigProps) {
  const def = PATTERN_CONFIG[patternType];
  if (!def) return null;

  const steps = useMemo(() => buildSteps(def, config), [def, config]);

  const globalModel = (config.model as string) ?? '';
  const stepsConfig = (config.steps as Record<string, StepConfig>) ?? {};

  const handleFieldChange = (key: string, value: string) => {
    const field = def.fields.find((f) => f.key === key);
    const parsed = field?.type === 'number' ? Number(value) : value;
    onChange({ ...config, [key]: parsed });
  };

  const handleStepChange = (stepKey: string, model: string, prompt: string) => {
    const updated: StepConfig = {};
    if (model) updated.model = model;
    if (prompt) updated.prompt = prompt;

    const newSteps = { ...stepsConfig };
    if (Object.keys(updated).length === 0) {
      delete newSteps[stepKey];
    } else {
      newSteps[stepKey] = updated;
    }
    onChange({ ...config, steps: Object.keys(newSteps).length > 0 ? newSteps : undefined });
  };

  const stepsBadge = steps.length > 0 ? (
    <span className="text-[9px] px-1.5 py-0.5 font-medium" style={{ color: '#e8a020', background: 'rgba(232,160,32,0.12)' }}>
      {steps.length}
    </span>
  ) : undefined;

  return (
    <div className="space-y-0">
      {/* Pattern type badge */}
      <div className="flex items-center gap-2 px-2.5 py-1.5 border-b border-[#252528]/30">
        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-violet-900/40 text-violet-300 border border-violet-700/30">
          {def.label}
        </span>
      </div>

      {/* Config — numeric fields + FSM states */}
      {(def.fields.length > 0 || patternType === 'fsm') && (
        <CollapsibleSection title="Config" defaultOpen>
          <div className="space-y-1.5">
            {def.fields.map((field) => (
              <label key={field.key} className="flex items-center justify-between gap-2">
                <span className="text-[11px] text-[#80808a]">{field.label}</span>
                <input
                  type={field.type}
                  value={(config[field.key] as string | number) ?? field.default}
                  onChange={(e) => handleFieldChange(field.key, e.target.value)}
                  className="w-16 px-1.5 py-0.5 text-[11px] bg-[#1a1a1d] border border-[#252528] rounded text-[#f0f0f0] text-right"
                  min={field.type === 'number' ? 1 : undefined}
                />
              </label>
            ))}
            {patternType === 'fsm' && (
              <label className="flex flex-col gap-0.5">
                <span className="text-[11px] text-[#80808a]">States (comma-separated)</span>
                <input
                  type="text"
                  value={(config.states as string) ?? ''}
                  onChange={(e) => onChange({ ...config, states: e.target.value })}
                  placeholder="plan,research,write,review"
                  className="w-full px-1.5 py-0.5 text-[11px] bg-[#1a1a1d] border border-[#252528] rounded text-[#f0f0f0] font-mono"
                />
              </label>
            )}
          </div>
        </CollapsibleSection>
      )}

      {/* Model — global default */}
      <CollapsibleSection title="Model">
        <ModelSelect
          value={globalModel}
          onChange={(v) => onChange({ ...config, model: v || undefined })}
        />
        <p className="text-[10px] text-[#4a4a52] mt-0.5">Default for all steps that don't override.</p>
      </CollapsibleSection>

      {/* Steps — per-step overrides */}
      {steps.length > 0 && (
        <CollapsibleSection title="Steps" badge={stepsBadge}>
          <div className="space-y-1">
            {steps.map((step) => {
              const stepCfg = stepsConfig[step.key] ?? {};
              return (
                <PatternStepEditor
                  key={step.key}
                  stepKey={step.key}
                  label={step.label}
                  model={stepCfg.model ?? ''}
                  prompt={stepCfg.prompt ?? ''}
                  onChange={(m, p) => handleStepChange(step.key, m, p)}
                />
              );
            })}
          </div>
        </CollapsibleSection>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/jetson/.openclaw/workspace/binex/.worktrees/design/amber-redesign/ui
npx tsc --noEmit 2>&1 | head -40
```

Expected: zero errors from PatternConfig.tsx and PatternStepEditor.tsx

- [ ] **Step 3: Commit**

```bash
cd /home/jetson/.openclaw/workspace/binex/.worktrees/design/amber-redesign
git add ui/src/components/editor/PatternConfig.tsx
git commit -m "feat(editor): rewrite PatternConfig with PATTERN_STEPS registry and step editors"
```

---

### Task 4: Update `graph-to-yaml.ts` for pattern node serialization

Pattern nodes use `pattern: critic` (not `agent: pattern://critic`) in YAML, plus top-level `model` and `steps` blocks.

**Files:**
- Modify: `ui/src/lib/graph-to-yaml.ts`

- [ ] **Step 1: Add pattern node handling in `graphToYaml`**

In `ui/src/lib/graph-to-yaml.ts`, find the `for (const node of nodes)` loop. The entry object is currently always built with `agent`. Add pattern detection before the `agent` line:

Find this block (around line 20-26):
```ts
  for (const node of nodes) {
    const d = node.data;
    const entry: Record<string, unknown> = {
      agent: d.agent ?? 'local://echo',
      outputs: ['output'],
    };
```

Replace with:
```ts
  for (const node of nodes) {
    const d = node.data;
    const isPattern = typeof d.agent === 'string' && d.agent.startsWith('pattern://');
    const entry: Record<string, unknown> = { outputs: ['output'] };

    if (isPattern) {
      entry.pattern = (d.agent as string).replace('pattern://', '');
      // Global default model
      const globalModel = d.config?.model as string | undefined;
      if (globalModel) entry.model = `llm://${globalModel}`;
      // Per-step config
      const stepsConfig = d.config?.steps as Record<string, { model?: string; prompt?: string }> | undefined;
      if (stepsConfig) {
        const stepsOut: Record<string, Record<string, string>> = {};
        for (const [key, sc] of Object.entries(stepsConfig)) {
          const stepEntry: Record<string, string> = {};
          if (sc.model) stepEntry.model = `llm://${sc.model}`;
          if (sc.prompt) stepEntry.prompt = sc.prompt;
          if (Object.keys(stepEntry).length > 0) stepsOut[key] = stepEntry;
        }
        if (Object.keys(stepsOut).length > 0) entry.steps = stepsOut;
      }
    } else {
      entry.agent = d.agent ?? 'local://echo';
    }
```

- [ ] **Step 2: Exclude pattern-only fields from the config block**

Find the `config` block (around line 31-36):
```ts
    const config: Record<string, unknown> = {};
    if (d.config?.max_tokens) config.max_tokens = d.config.max_tokens;
    if (d.config?.temperature != null) config.temperature = d.config.temperature;
    if (d.config?.budget_limit) config.budget_limit = d.config.budget_limit;
    if (d.config?.skill) config.skill = d.config.skill;
    if (Object.keys(config).length > 0) entry.config = config;
```

Replace with:
```ts
    const config: Record<string, unknown> = {};
    if (!isPattern) {
      if (d.config?.max_tokens) config.max_tokens = d.config.max_tokens;
      if (d.config?.temperature != null) config.temperature = d.config.temperature;
      if (d.config?.budget_limit) config.budget_limit = d.config.budget_limit;
      if (d.config?.skill) config.skill = d.config.skill;
    } else {
      // Pattern numeric fields (rounds, agents, variants, max_iterations, max_workers)
      const numericFields = ['rounds', 'agents', 'variants', 'max_iterations', 'max_workers'];
      for (const f of numericFields) {
        if (d.config?.[f] != null) config[f] = d.config[f];
      }
      // FSM states
      if (d.config?.states) {
        const raw = d.config.states as string;
        config.states = raw.split(',').map((s: string) => s.trim()).filter(Boolean);
      }
    }
    if (Object.keys(config).length > 0) entry.config = config;
```

- [ ] **Step 3: Exclude `system_prompt` for pattern nodes**

Find this block (around line 27-30):
```ts
    // system_prompt is top-level in YAML (used by LLM and Human adapters)
    const promptText = d.system_prompt ?? d.config?.system_prompt ?? d.config?.prompt_message;
    if (promptText) entry.system_prompt = promptText;
```

Replace with:
```ts
    if (!isPattern) {
      const promptText = d.system_prompt ?? d.config?.system_prompt ?? d.config?.prompt_message;
      if (promptText) entry.system_prompt = promptText;
    }
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd /home/jetson/.openclaw/workspace/binex/.worktrees/design/amber-redesign/ui
npx tsc --noEmit 2>&1 | head -30
```

Expected: zero errors

- [ ] **Step 5: Commit**

```bash
cd /home/jetson/.openclaw/workspace/binex/.worktrees/design/amber-redesign
git add ui/src/lib/graph-to-yaml.ts
git commit -m "feat(editor): serialize pattern nodes with model/steps in graphToYaml"
```

---

### Task 5: Update `yamlToRfGraph` for pattern node deserialization

**Files:**
- Modify: `ui/src/pages/WorkflowEditor.tsx`

- [ ] **Step 1: Extend `ParsedYamlWorkflow` node spec type**

Find `ParsedYamlWorkflow` interface (around line 47). The nodes record type is:
```ts
nodes?: Record<string, { agent: string; depends_on?: string[]; config?: Record<string, unknown>; system_prompt?: string; inputs?: Record<string, string>; outputs?: string[]; tools?: string[]; cao?: Record<string, unknown> }>;
```

Replace with:
```ts
nodes?: Record<string, {
  agent?: string;
  pattern?: string;
  model?: string;
  steps?: Record<string, { model?: string; prompt?: string }>;
  depends_on?: string[];
  config?: Record<string, unknown>;
  system_prompt?: string;
  inputs?: Record<string, string>;
  outputs?: string[];
  tools?: string[];
  cao?: Record<string, unknown>;
}>;
```

- [ ] **Step 2: Handle pattern nodes in `yamlToRfGraph`**

Find the `nodes.map` call inside `yamlToRfGraph` (around line 67). The current code:
```ts
  const nodes: Node[] = entries.map(([id, spec], i) => {
    const agent = spec.agent ?? 'local://echo';
    const { nodeType, color } = agentToNodeType(agent);
    return {
      id,
      type: 'editable',
      position: { x: 250, y: i * 120 + 50 },
      data: {
        label: id,
        nodeType,
        agent,
        config: { ...spec.config, ...(spec.system_prompt ? { system_prompt: spec.system_prompt } : {}), ...(spec.cao ?? {}) },
        system_prompt: spec.system_prompt,
        inputs: spec.inputs,
        outputs: spec.outputs,
        tools: spec.tools ?? [],
        color,
      },
    };
  });
```

Replace with:
```ts
  const nodes: Node[] = entries.map(([id, spec], i) => {
    const isPattern = !!spec.pattern;
    const agent = isPattern ? `pattern://${spec.pattern}` : (spec.agent ?? 'local://echo');
    const { nodeType, color } = isPattern
      ? { nodeType: 'pattern', color: '#a78bfa' }
      : agentToNodeType(agent);

    // Parse pattern model (strip llm:// prefix for storage in config)
    const patternModel = spec.model?.startsWith('llm://')
      ? spec.model.slice(6)
      : spec.model;

    // Parse per-step configs (strip llm:// from step models)
    const parsedSteps = spec.steps
      ? Object.fromEntries(
          Object.entries(spec.steps).map(([k, v]) => [
            k,
            {
              model: v.model?.startsWith('llm://') ? v.model.slice(6) : (v.model ?? ''),
              prompt: v.prompt ?? '',
            },
          ]),
        )
      : undefined;

    const config: Record<string, unknown> = {
      ...spec.config,
      ...(spec.system_prompt ? { system_prompt: spec.system_prompt } : {}),
      ...(spec.cao ?? {}),
    };
    if (isPattern) {
      if (patternModel) config.model = patternModel;
      if (parsedSteps) config.steps = parsedSteps;
      // FSM: states array → comma-separated string for the UI input
      if (Array.isArray(config.states)) {
        config.states = (config.states as string[]).join(',');
      }
    }

    return {
      id,
      type: 'editable',
      position: { x: 250, y: i * 120 + 50 },
      data: {
        label: id,
        nodeType,
        agent,
        config,
        system_prompt: spec.system_prompt,
        inputs: spec.inputs,
        outputs: spec.outputs,
        tools: spec.tools ?? [],
        color,
      },
    };
  });
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /home/jetson/.openclaw/workspace/binex/.worktrees/design/amber-redesign/ui
npx tsc --noEmit 2>&1 | head -30
```

Expected: zero errors

- [ ] **Step 4: Commit**

```bash
cd /home/jetson/.openclaw/workspace/binex/.worktrees/design/amber-redesign
git add ui/src/pages/WorkflowEditor.tsx
git commit -m "feat(editor): parse pattern model/steps in yamlToRfGraph"
```

---

### Task 6: Expand pattern node width to 280px in `EditableNode`

**Files:**
- Modify: `ui/src/components/editor/EditableNode.tsx`

- [ ] **Step 1: Update expanded node width for pattern nodes**

Find line ~139:
```ts
    <div style={{ ...nodeBase, width: 260 }} className="nowheel">
```

Replace with:
```ts
    <div style={{ ...nodeBase, width: agent.startsWith('pattern://') ? 280 : 260 }} className="nowheel">
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/jetson/.openclaw/workspace/binex/.worktrees/design/amber-redesign/ui
npx tsc --noEmit 2>&1 | head -30
```

Expected: zero errors

- [ ] **Step 3: Commit**

```bash
cd /home/jetson/.openclaw/workspace/binex/.worktrees/design/amber-redesign
git add ui/src/components/editor/EditableNode.tsx
git commit -m "feat(editor): widen pattern nodes to 280px for step model select"
```

---

### Task 7: Full build and visual verification

**Files:**
- No changes — run build script and verify in browser

- [ ] **Step 1: Run build**

```bash
cd /home/jetson/.openclaw/workspace/binex/.worktrees/design/amber-redesign
bash scripts/build-ui.sh 2>&1 | tail -20
```

Expected: `✓ built in X.Xs` with no TypeScript errors

- [ ] **Step 2: Start dev server and open browser**

```bash
cd /home/jetson/.openclaw/workspace/binex/.worktrees/design/amber-redesign/ui
npm run dev &
```

Open `http://localhost:5173`. Navigate to the Workflow Editor.

- [ ] **Step 3: Visual checks**

1. Drag a **pattern node** (e.g. Critic) onto the canvas. Click to expand.
2. Verify three sections appear: **Config** (Rounds field), **Model** (ModelSelect), **Steps** (badge showing "3").
3. Open **Model** section, pick a model — it should appear as the global default.
4. Open **Steps**, expand "Draft" row. Verify collapsed shows "inherit" in muted italic.
5. In the Draft step, verify ModelSelect shows "[default model]" row at top. Pick a model — collapsed row should update.
6. Enter a prompt in the textarea.
7. Click "YAML" tab — verify generated YAML shows:
   - `pattern: critic` (not `agent: pattern://critic`)
   - `model: llm://...` at node level (if set)
   - `steps.draft.model: llm://...` and `steps.draft.prompt: ...`
8. Paste the YAML back (YAML→Graph) — verify the model and prompt survive the round-trip.
9. Test FSM pattern: verify "States" text input appears, entering `plan,research,write` regenerates the Steps list with those three steps.

- [ ] **Step 4: Final commit**

```bash
cd /home/jetson/.openclaw/workspace/binex/.worktrees/design/amber-redesign
git add -A
git commit -m "feat(editor): pattern step editor — per-step model/prompt overrides"
```

---

## Self-Review

**Spec coverage:**
- ✅ PatternStepEditor component with collapsed/expanded state
- ✅ PATTERN_STEPS registry for all 9 pattern types
- ✅ Global default model section in PatternConfig
- ✅ Steps section with badge count
- ✅ ModelSelect with `[default model]` inherit option (value `""`)
- ✅ YAML serialization: `pattern:` key, `model:`, `steps:` (omit empty)
- ✅ YAML deserialization: `pattern` → `pattern://` agent, model/steps parsed
- ✅ FSM states: comma-separated text input, regenerates step list
- ✅ Node width 280px for pattern nodes
- ✅ Step count badge

**Type consistency:** `PatternStepEditorProps.model/prompt` are `string` (not `string | undefined`) throughout. `StepConfig` in PatternConfig uses optional fields but always resolved to `''` before passing to `PatternStepEditor`. `parsedSteps` in `yamlToRfGraph` maps to the same shape.

**Serialization round-trip:** `model` stored in config without `llm://` prefix (stripped on read, re-added on write). FSM `states` stored as comma-separated string in UI, serialized as `string[]` in YAML.
