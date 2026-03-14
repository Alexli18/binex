const MODEL_TIERS = [
  {
    label: 'Frontier',
    models: ['gpt-5.4', 'claude-sonnet-4-6', 'claude-opus-4-6', 'gemini-3.1-pro'],
  },
  {
    label: 'Fast / Cheap',
    models: ['gpt-4o-mini', 'claude-haiku-4-5', 'gemini-2.5-flash'],
  },
  {
    label: 'Open Source',
    models: ['ollama/llama3.3', 'ollama/qwen3.5', 'deepseek/deepseek-chat'],
  },
  {
    label: 'OpenRouter Free',
    models: [
      'openrouter/qwen3-coder-480b:free',
      'openrouter/llama-3.3-70b:free',
      'openrouter/gemma-3-27b:free',
      'openrouter/mistral-small-3.1-24b:free',
      'openrouter/hermes-3-405b:free',
      'openrouter/gpt-oss-120b:free',
      'openrouter/nemotron-3-super-120b:free',
      'openrouter/glm-4.5-air:free',
    ],
  },
];

interface ModelSelectProps {
  value: string;
  onChange: (model: string) => void;
}

export function ModelSelect({ value, onChange }: ModelSelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
    >
      {MODEL_TIERS.map((tier) => (
        <optgroup key={tier.label} label={tier.label}>
          {tier.models.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}
