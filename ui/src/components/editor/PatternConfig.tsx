import { CollapsibleSection } from './CollapsibleSection';

// Pattern-specific config fields
const PATTERN_CONFIG: Record<string, { label: string; fields: Array<{ key: string; label: string; type: 'number' | 'text'; default: number | string }> }> = {
  critic: {
    label: 'Critic',
    fields: [
      { key: 'rounds', label: 'Rounds', type: 'number', default: 1 },
    ],
  },
  debate: {
    label: 'Debate',
    fields: [
      { key: 'agents', label: 'Agents', type: 'number', default: 2 },
      { key: 'rounds', label: 'Rounds', type: 'number', default: 1 },
    ],
  },
  best_of_n: {
    label: 'Best of N',
    fields: [
      { key: 'variants', label: 'Variants', type: 'number', default: 3 },
    ],
  },
  reflexion: {
    label: 'Reflexion',
    fields: [
      { key: 'max_iterations', label: 'Max Iterations', type: 'number', default: 3 },
    ],
  },
  scatter: {
    label: 'Scatter',
    fields: [
      { key: 'max_workers', label: 'Max Workers', type: 'number', default: 10 },
    ],
  },
  fsm: {
    label: 'State Machine',
    fields: [
      { key: 'max_iterations', label: 'Max Iterations', type: 'number', default: 10 },
    ],
  },
  constitutional: {
    label: 'Constitutional',
    fields: [],
  },
  chain_of_verification: {
    label: 'Verify Chain',
    fields: [],
  },
  plan_execute: {
    label: 'Plan & Execute',
    fields: [
      { key: 'max_iterations', label: 'Max Iterations', type: 'number', default: 3 },
    ],
  },
};

interface PatternConfigProps {
  patternType: string;
  config: Record<string, unknown>;
  onChange: (config: Record<string, unknown>) => void;
}

export function PatternConfig({ patternType, config, onChange }: PatternConfigProps) {
  const patternDef = PATTERN_CONFIG[patternType];
  if (!patternDef) return null;

  const handleFieldChange = (key: string, value: string) => {
    const field = patternDef.fields.find((f) => f.key === key);
    const parsed = field?.type === 'number' ? Number(value) : value;
    onChange({ ...config, [key]: parsed });
  };

  return (
    <div className="space-y-2">
      {/* Pattern type badge */}
      <div className="flex items-center gap-2">
        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-pink-900/40 text-pink-300 border border-pink-700/30">
          {patternDef.label}
        </span>
      </div>

      {/* Pattern-specific fields */}
      {patternDef.fields.length > 0 && (
        <CollapsibleSection title="Pattern Config" defaultOpen>
          <div className="space-y-2">
            {patternDef.fields.map((field) => (
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
          </div>
        </CollapsibleSection>
      )}

      {/* Steps section (per-step model/prompt overrides) */}
      <CollapsibleSection title="Step Overrides">
        <p className="text-[10px] text-[#4a4a52]">
          Configure per-step model and prompt overrides in the YAML editor.
        </p>
      </CollapsibleSection>
    </div>
  );
}
