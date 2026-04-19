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
  max_retries?: number;
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

  const handleStepChange = (stepKey: string, model: string, prompt: string, maxRetries: number | undefined) => {
    const updated: StepConfig = {};
    if (model) updated.model = model;
    if (prompt) updated.prompt = prompt;
    if (maxRetries !== undefined) updated.max_retries = maxRetries;

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
                  maxRetries={stepCfg.max_retries}
                  onChange={(m, p, r) => handleStepChange(step.key, m, p, r)}
                />
              );
            })}
          </div>
        </CollapsibleSection>
      )}
    </div>
  );
}
