import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Sparkles, Zap, Box, Gift, Brain, ChevronDown, Clock, Search, Gauge, PenLine } from 'lucide-react';
import { useProviders, type ApiProvider } from '@/hooks/useProviders';

// --- Tier display config ---

type TierKey = 'flagship' | 'balanced' | 'fast' | 'reasoning' | 'free' | 'local';

const TIER_CONFIG: Record<TierKey, { label: string; icon: typeof Sparkles; iconClass: string }> = {
  flagship:  { label: 'Flagship',  icon: Sparkles, iconClass: 'text-amber-400' },
  balanced:  { label: 'Balanced',  icon: Gauge,    iconClass: 'text-sky-400' },
  fast:      { label: 'Fast',      icon: Zap,      iconClass: 'text-green-400' },
  reasoning: { label: 'Reasoning', icon: Brain,    iconClass: 'text-rose-400' },
  free:      { label: 'Free',      icon: Gift,     iconClass: 'text-[#80808a]' },
  local:     { label: 'Local',     icon: Box,      iconClass: 'text-amber-400' },
};

// --- Fallback data (used when API is unavailable) ---

const FALLBACK_PROVIDERS: ApiProvider[] = [
  {
    name: 'openai', default_model: 'gpt-5.4', env_var: 'OPENAI_API_KEY', agent_prefix: 'llm://', configured: true,
    models: [
      { id: 'gpt-5.4', tier: 'flagship', context_k: 128 },
      { id: 'gpt-4o-mini', tier: 'fast', context_k: 128 },
    ],
  },
  {
    name: 'anthropic', default_model: 'claude-sonnet-4-6', env_var: 'ANTHROPIC_API_KEY', agent_prefix: 'llm://', configured: true,
    models: [
      { id: 'claude-opus-4-6', tier: 'flagship', context_k: 200 },
      { id: 'claude-sonnet-4-6', tier: 'flagship', context_k: 200 },
      { id: 'claude-haiku-4-5', tier: 'fast', context_k: 200 },
    ],
  },
  {
    name: 'google', default_model: 'gemini-3.1-pro', env_var: 'GOOGLE_API_KEY', agent_prefix: 'llm://', configured: true,
    models: [
      { id: 'gemini-3.1-pro', tier: 'flagship', context_k: 2000 },
      { id: 'gemini-2.5-flash', tier: 'fast', context_k: 1000 },
    ],
  },
  {
    name: 'ollama', default_model: 'ollama/llama3.3', env_var: '', agent_prefix: 'llm://', configured: false,
    models: [
      { id: 'ollama/llama3.3', tier: 'local', context_k: 128 },
      { id: 'ollama/qwen3.5', tier: 'local', context_k: 128 },
    ],
  },
  {
    name: 'deepseek', default_model: 'deepseek/deepseek-chat', env_var: 'DEEPSEEK_API_KEY', agent_prefix: 'llm://', configured: false,
    models: [
      { id: 'deepseek/deepseek-chat', tier: 'reasoning', context_k: 64 },
    ],
  },
  {
    name: 'openrouter', default_model: 'openrouter/qwen/qwen3-coder-480b:free', env_var: 'OPENROUTER_API_KEY', agent_prefix: 'llm://', configured: false,
    models: [
      { id: 'openrouter/qwen/qwen3-coder-480b:free', tier: 'free', context_k: 128 },
      { id: 'openrouter/meta-llama/llama-3.3-70b-instruct:free', tier: 'free', context_k: 128 },
      { id: 'openrouter/google/gemma-3-27b-it:free', tier: 'free', context_k: 96 },
      { id: 'openrouter/mistralai/mistral-small-3.1-24b-instruct:free', tier: 'free', context_k: null },
      { id: 'openrouter/nousresearch/hermes-3-llama-3.1-405b:free', tier: 'free', context_k: null },
      { id: 'openrouter/openai/gpt-oss-120b:free', tier: 'free', context_k: null },
      { id: 'openrouter/nvidia/llama-3.1-nemotron-ultra-253b:free', tier: 'free', context_k: null },
      { id: 'openrouter/zhipuai/glm-4-air:free', tier: 'free', context_k: null },
    ],
  },
];

// --- Provider badge colors ---

const PROVIDER_COLORS: Record<string, string> = {
  openai: 'bg-emerald-500/15 text-emerald-400',
  anthropic: 'bg-orange-500/15 text-orange-400',
  google: 'bg-amber-500/15 text-amber-400',
  gemini: 'bg-amber-500/15 text-amber-400',
  ollama: 'bg-[#4a4a52]/15 text-[#80808a]',
  deepseek: 'bg-cyan-500/15 text-cyan-400',
  openrouter: 'bg-violet-500/15 text-violet-400',
  groq: 'bg-red-500/15 text-red-400',
  mistral: 'bg-amber-500/15 text-amber-400',
  together: 'bg-amber-500/15 text-amber-400',
};

function shortName(id: string): string {
  return id
    .replace(/^openrouter\/[^/]+\//, '')
    .replace(/:free$/, '');
}

// --- Recently Used (localStorage) ---

const RECENT_KEY = 'binex:recent-models';
const MAX_RECENT = 3;

function getRecent(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function addRecent(modelId: string) {
  const list = getRecent().filter((m) => m !== modelId);
  list.unshift(modelId);
  localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, MAX_RECENT)));
}

// --- Flat model entry for rendering ---

interface FlatModel {
  id: string;
  provider: string;
  tier: TierKey;
  context_k: number | null;
  configured: boolean;
}

// --- Component ---

interface ModelSelectProps {
  value: string;
  onChange: (model: string) => void;
}

// Provider prefixes for custom model input
const PROVIDER_PREFIXES: { name: string; prefix: string }[] = [
  { name: 'OpenAI', prefix: '' },
  { name: 'Anthropic', prefix: '' },
  { name: 'Gemini', prefix: 'gemini/' },
  { name: 'Ollama', prefix: 'ollama/' },
  { name: 'OpenRouter', prefix: 'openrouter/' },
  { name: 'Groq', prefix: 'groq/' },
  { name: 'DeepSeek', prefix: 'deepseek/' },
  { name: 'Mistral', prefix: 'mistral/' },
  { name: 'Together', prefix: 'together_ai/' },
];

export function ModelSelect({ value, onChange }: ModelSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [highlightIdx, setHighlightIdx] = useState(0);
  const [customMode, setCustomMode] = useState<string | null>(null); // provider prefix for custom
  const [customModel, setCustomModel] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const customInputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const { data: providersData } = useProviders();
  const providers = providersData?.providers ?? FALLBACK_PROVIDERS;

  const recent = useMemo(() => getRecent(), [open]); // eslint-disable-line react-hooks/exhaustive-deps

  // Split into configured / unconfigured, flatten models
  const { configuredModels, unconfiguredModels, allModelIds } = useMemo(() => {
    const conf: Array<{ provider: ApiProvider; models: FlatModel[] }> = [];
    const unconf: Array<{ provider: ApiProvider; models: FlatModel[] }> = [];
    const ids: string[] = [];

    for (const p of providers) {
      const flat: FlatModel[] = p.models.map((m) => ({
        id: m.id,
        provider: p.name,
        tier: m.tier,
        context_k: m.context_k,
        configured: p.configured,
      }));
      ids.push(...flat.map((m) => m.id));
      const entry = { provider: p, models: flat };
      if (p.configured) conf.push(entry);
      else unconf.push(entry);
    }

    return { configuredModels: conf, unconfiguredModels: unconf, allModelIds: ids };
  }, [providers]);

  // Filter by search
  const filter = useCallback((models: FlatModel[], q: string) => {
    if (!q) return models;
    return models.filter(
      (m) => m.id.toLowerCase().includes(q) || m.provider.toLowerCase().includes(q) || shortName(m.id).toLowerCase().includes(q)
    );
  }, []);

  const q = search.toLowerCase().trim();

  const filteredConfigured = useMemo(
    () => configuredModels.map((g) => ({ ...g, models: filter(g.models, q) })).filter((g) => g.models.length > 0),
    [configuredModels, q, filter]
  );
  const filteredUnconfigured = useMemo(
    () => unconfiguredModels.map((g) => ({ ...g, models: filter(g.models, q) })).filter((g) => g.models.length > 0),
    [unconfiguredModels, q, filter]
  );

  // Flat list for keyboard nav
  const flatItems = useMemo(() => {
    const items: string[] = [];
    if (!q && recent.length > 0) {
      recent.forEach((r) => items.push(r));
    }
    filteredConfigured.forEach((g) => g.models.forEach((m) => items.push(m.id)));
    filteredUnconfigured.forEach((g) => g.models.forEach((m) => items.push(m.id)));
    if (q && !allModelIds.includes(q)) {
      items.push(`__custom__:${q}`);
    }
    return items;
  }, [filteredConfigured, filteredUnconfigured, q, recent, allModelIds]);

  useEffect(() => { setHighlightIdx(0); }, [search]);

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 0);
    else { setSearch(''); setCustomMode(null); setCustomModel(''); }
  }, [open]);

  useEffect(() => {
    if (!open || !listRef.current) return;
    const items = listRef.current.querySelectorAll('[data-model-item]');
    items[highlightIdx]?.scrollIntoView({ block: 'nearest' });
  }, [highlightIdx, open]);

  const selectModel = useCallback((modelId: string) => {
    const actualId = modelId.startsWith('__custom__:') ? modelId.slice(11) : modelId;
    onChange(actualId);
    addRecent(actualId);
    setOpen(false);
    setSearch('');
  }, [onChange]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setHighlightIdx((i) => Math.min(i + 1, flatItems.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlightIdx((i) => Math.max(i - 1, 0)); }
    else if (e.key === 'Enter') { e.preventDefault(); if (flatItems[highlightIdx]) selectModel(flatItems[highlightIdx]); }
    else if (e.key === 'Escape') { setOpen(false); }
  }, [flatItems, highlightIdx, selectModel]);

  // Find provider for current value
  const currentProvider = useMemo(() => {
    for (const p of providers) {
      if (p.models.some((m) => m.id === value)) return p.name;
    }
    return null;
  }, [providers, value]);

  const displayName = shortName(value) || 'Select model...';

  return (
    <div ref={containerRef} className="relative" onClick={(e) => e.stopPropagation()}>
      {/* Trigger */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between bg-[#252528] border border-[#333338] rounded px-2 py-1 text-xs text-[#f0f0f0] hover:bg-[#333338]/80 focus:outline-none focus:border-amber-500 transition-colors"
      >
        <span className="truncate flex items-center gap-1.5">
          {currentProvider && (
            <span className={`px-1 py-0 rounded text-[9px] font-medium ${PROVIDER_COLORS[currentProvider] || 'bg-[#333338] text-[#80808a]'}`}>
              {currentProvider}
            </span>
          )}
          {displayName}
        </span>
        <ChevronDown size={12} className={`shrink-0 opacity-50 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 mt-1 w-full min-w-[280px] bg-[#1a1a1d] border border-[#333338] rounded-md shadow-xl shadow-black/40 overflow-hidden">
          {/* Search */}
          <div className="flex items-center gap-1.5 px-2 py-1.5 border-b border-[#252528]">
            <Search size={12} className="text-[#4a4a52] shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search models..."
              className="w-full bg-transparent text-xs text-[#f0f0f0] placeholder:text-[#4a4a52] outline-none"
            />
          </div>

          <div ref={listRef} className="max-h-[280px] overflow-y-auto">
            {/* Recently Used */}
            {!q && recent.length > 0 && (
              <div>
                <GroupHeader icon={Clock} iconClass="text-[#80808a]" label="Recent" />
                {recent.map((modelId, i) => (
                  <ModelRow
                    key={`recent-${modelId}`}
                    modelId={modelId}
                    providerName={providers.find((p) => p.models.some((m) => m.id === modelId))?.name}
                    isSelected={value === modelId}
                    isHighlighted={highlightIdx === i}
                    onSelect={() => selectModel(modelId)}
                    onHover={() => setHighlightIdx(i)}
                  />
                ))}
              </div>
            )}

            {/* Configured providers */}
            {filteredConfigured.map((group) => (
              <div key={group.provider.name}>
                <GroupHeader
                  label={group.provider.name}
                  configured
                  icon={tierIcon(group.models[0]?.tier)}
                  iconClass={tierIconClass(group.models[0]?.tier)}
                />
                {group.models.map((model) => {
                  const idx = flatItems.indexOf(model.id);
                  return (
                    <ModelRow
                      key={model.id}
                      modelId={model.id}
                      providerName={model.provider}
                      tier={model.tier}
                      contextK={model.context_k}
                      isSelected={value === model.id}
                      isHighlighted={highlightIdx === idx}
                      onSelect={() => selectModel(model.id)}
                      onHover={() => setHighlightIdx(idx)}
                    />
                  );
                })}
              </div>
            ))}

            {/* Separator */}
            {filteredConfigured.length > 0 && filteredUnconfigured.length > 0 && (
              <div className="border-t border-[#252528] my-0.5" />
            )}

            {/* Unconfigured providers */}
            {filteredUnconfigured.map((group) => (
              <div key={group.provider.name} className="opacity-60">
                <GroupHeader
                  label={group.provider.name}
                  configured={false}
                  icon={tierIcon(group.models[0]?.tier)}
                  iconClass={tierIconClass(group.models[0]?.tier)}
                />
                {group.models.map((model) => {
                  const idx = flatItems.indexOf(model.id);
                  return (
                    <ModelRow
                      key={model.id}
                      modelId={model.id}
                      providerName={model.provider}
                      tier={model.tier}
                      contextK={model.context_k}
                      isSelected={value === model.id}
                      isHighlighted={highlightIdx === idx}
                      onSelect={() => selectModel(model.id)}
                      onHover={() => setHighlightIdx(idx)}
                    />
                  );
                })}
              </div>
            ))}

            {/* Custom model — inline search match */}
            {q && !allModelIds.includes(q) && !customMode && (
              <div
                data-model-item
                className={`flex items-center gap-2 px-2 py-1.5 text-xs cursor-pointer transition-colors ${
                  highlightIdx === flatItems.length - 1
                    ? 'bg-amber-500/20 text-amber-300'
                    : 'text-amber-400 hover:bg-[#252528]'
                }`}
                onClick={() => selectModel(`__custom__:${q}`)}
                onMouseEnter={() => setHighlightIdx(flatItems.length - 1)}
              >
                Use custom: <span className="font-mono">{q}</span>
              </div>
            )}

            {filteredConfigured.length === 0 && filteredUnconfigured.length === 0 && !q && (
              <div className="py-4 text-center text-xs text-[#4a4a52]">No models available</div>
            )}

            {/* Custom model — provider picker */}
            {!customMode && (
              <div className="border-t border-[#252528] mt-0.5 pt-0.5">
                <GroupHeader icon={PenLine} iconClass="text-amber-400" label="Custom model" />
                <div className="flex flex-wrap gap-1 px-2 py-1.5">
                  {PROVIDER_PREFIXES.map((pp) => (
                    <button
                      key={pp.name}
                      type="button"
                      onClick={() => {
                        setCustomMode(pp.prefix);
                        setCustomModel('');
                        setTimeout(() => customInputRef.current?.focus(), 50);
                      }}
                      className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors
                        ${PROVIDER_COLORS[pp.name.toLowerCase()] || 'bg-[#333338]/50 text-[#80808a]'}
                        hover:opacity-80 cursor-pointer`}
                    >
                      {pp.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Custom model — input after provider selected */}
            {customMode !== null && (
              <div className="border-t border-[#252528] mt-0.5 p-2">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <button
                    type="button"
                    onClick={() => setCustomMode(null)}
                    className="text-[10px] text-[#80808a] hover:text-[#f0f0f0]"
                  >
                    ← Back
                  </button>
                  <span className="text-[10px] text-[#4a4a52]">Custom model</span>
                </div>
                <div className="flex items-center gap-1">
                  {customMode && (
                    <span className="text-[10px] text-[#80808a] font-mono shrink-0">{customMode}</span>
                  )}
                  <input
                    ref={customInputRef}
                    type="text"
                    value={customModel}
                    onChange={(e) => setCustomModel(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && customModel.trim()) {
                        e.preventDefault();
                        selectModel(customMode + customModel.trim());
                      } else if (e.key === 'Escape') {
                        setCustomMode(null);
                      }
                    }}
                    placeholder="model-name"
                    className="flex-1 bg-[#252528]/50 border border-[#333338] rounded px-2 py-1
                      text-xs text-[#f0f0f0] placeholder:text-[#4a4a52] focus:outline-none focus:border-amber-500 font-mono"
                  />
                  <button
                    type="button"
                    disabled={!customModel.trim()}
                    onClick={() => { if (customModel.trim()) selectModel(customMode + customModel.trim()); }}
                    className="px-2 py-1 rounded bg-amber-500 text-black text-[10px] font-medium
                      hover:bg-amber-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
                  >
                    Use
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// --- Helpers ---

function tierIcon(tier?: TierKey): typeof Sparkles {
  return tier ? (TIER_CONFIG[tier]?.icon ?? Box) : Box;
}

function tierIconClass(tier?: TierKey): string {
  return tier ? (TIER_CONFIG[tier]?.iconClass ?? 'text-[#80808a]') : 'text-[#80808a]';
}

// --- GroupHeader ---

function GroupHeader({ label, icon: Icon, iconClass, configured }: {
  label: string;
  icon: typeof Sparkles;
  iconClass: string;
  configured?: boolean;
}) {
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 text-[10px] font-medium text-[#4a4a52] uppercase tracking-wider">
      {configured !== undefined && (
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${configured ? 'bg-green-500' : 'bg-[#333338]'}`} />
      )}
      <Icon size={10} className={iconClass} />
      {label}
    </div>
  );
}

// --- ModelRow ---

function ModelRow({
  modelId,
  providerName,
  tier,
  contextK,
  isSelected,
  isHighlighted,
  onSelect,
  onHover,
}: {
  modelId: string;
  providerName?: string;
  tier?: TierKey;
  contextK?: number | null;
  isSelected: boolean;
  isHighlighted: boolean;
  onSelect: () => void;
  onHover: () => void;
}) {
  const prov = providerName ?? 'custom';
  const tierCfg = tier ? TIER_CONFIG[tier] : null;

  return (
    <div
      data-model-item
      className={`flex items-center gap-1.5 px-2 py-1.5 text-xs cursor-pointer transition-colors ${
        isHighlighted ? 'bg-[#252528]' : 'hover:bg-[#252528]/50'
      } ${isSelected ? 'text-amber-300' : 'text-[#80808a]'}`}
      onClick={onSelect}
      onMouseEnter={onHover}
    >
      <span className={`shrink-0 px-1 py-0 rounded text-[9px] font-medium ${PROVIDER_COLORS[prov] || 'bg-[#333338] text-[#80808a]'}`}>
        {prov}
      </span>
      <span className="flex-1 truncate">{shortName(modelId)}</span>
      {contextK != null && (
        <span className="text-[9px] text-[#4a4a52] tabular-nums shrink-0">{contextK}k</span>
      )}
      {tierCfg && (
        <span className={`text-[9px] ${tierCfg.iconClass}`}>{tierCfg.label}</span>
      )}
      {isSelected && (
        <span className="text-amber-400 text-[10px]">✓</span>
      )}
    </div>
  );
}
