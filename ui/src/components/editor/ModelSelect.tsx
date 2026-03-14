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
      'openrouter/qwen/qwen3-coder-480b:free',
      'openrouter/meta-llama/llama-3.3-70b-instruct:free',
      'openrouter/google/gemma-3-27b-it:free',
      'openrouter/mistralai/mistral-small-3.1-24b-instruct:free',
      'openrouter/nousresearch/hermes-3-llama-3.1-405b:free',
      'openrouter/openai/gpt-oss-120b:free',
      'openrouter/nvidia/llama-3.1-nemotron-ultra-253b:free',
      'openrouter/zhipuai/glm-4-air:free',
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
