import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Wand2, Layout, FileText, ArrowRight, Copy, Check, GitBranch, Settings, User, Globe, Star, Brain, TerminalSquare } from 'lucide-react';
import { usePatterns, useScaffold } from '../hooks/useUtilities';
import type { Pattern } from '../hooks/useUtilities';
import { Breadcrumb } from '@/components/common/Breadcrumb';
import { PageShell } from '@/components/layout/PageShell';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

type Mode = 'dsl' | 'template' | 'blank';

const BLANK_YAML = `name: my-workflow
description: A new workflow

nodes:
  step_1:
    agent: "llm://openai/gpt-4o-mini"
    prompt: "Your prompt here"

  step_2:
    agent: "llm://openai/gpt-4o-mini"
    prompt: "Next step"
    depends_on:
      - step_1
`;

const TAB_CONFIG: { mode: Mode; label: string; icon: typeof Wand2 }[] = [
  { mode: 'dsl', label: 'DSL', icon: Wand2 },
  { mode: 'template', label: 'Template', icon: Layout },
  { mode: 'blank', label: 'Blank', icon: FileText },
];

// Category metadata — labels, icons, colors. Patterns are grouped by API `category` field.
const CATEGORY_META: Record<string, { label: string; description: string; icon: typeof GitBranch; color: string }> = {
  core:        { label: 'Core Topologies',    description: 'Fundamental DAG patterns',          icon: GitBranch, color: 'blue' },
  control:     { label: 'Workflow Control',   description: 'Review loops, validation, routing', icon: Settings,  color: 'purple' },
  human:       { label: 'Human-in-the-Loop',  description: 'Approval gates and feedback',       icon: User,      color: 'green' },
  integration: { label: 'Integration',        description: 'A2A, multi-provider, security',     icon: Globe,     color: 'orange' },
  cao:         { label: 'CLI Agents (CAO)',   description: 'CLI AI agents via tmux terminals',  icon: TerminalSquare, color: 'cyan' },
  agentic:     { label: 'Agentic Patterns',  description: 'AI reasoning and self-improvement', icon: Brain,     color: 'rose' },
};

// Display order for categories
const CATEGORY_ORDER = ['core', 'control', 'human', 'integration', 'cao', 'agentic'];

const CATEGORY_COLORS: Record<string, { border: string; text: string; dot: string; bg: string }> = {
  blue:   { border: 'border-l-amber-500',   text: 'text-amber-400',   dot: 'bg-amber-400',   bg: 'bg-amber-500/5' },
  purple: { border: 'border-l-violet-500', text: 'text-violet-400', dot: 'bg-violet-400', bg: 'bg-violet-500/5' },
  green:  { border: 'border-l-emerald-500', text: 'text-emerald-400', dot: 'bg-emerald-400', bg: 'bg-emerald-500/5' },
  orange: { border: 'border-l-orange-500', text: 'text-orange-400', dot: 'bg-orange-400', bg: 'bg-orange-500/5' },
  cyan:   { border: 'border-l-cyan-500',   text: 'text-cyan-400',   dot: 'bg-cyan-400',   bg: 'bg-cyan-500/5' },
  rose:   { border: 'border-l-rose-500',   text: 'text-rose-400',   dot: 'bg-rose-400',   bg: 'bg-rose-500/5' },
};

// Popular patterns get a badge
const POPULAR_PATTERNS = new Set(['fan-out-fan-in', 'research', 'human-feedback']);

// --- MiniGraph: SVG topology preview ---

function MiniGraph({ dsl, color }: { dsl: string; color: string }) {
  if (!dsl) return null;
  const layers = dsl.split('->').map(l => l.trim().split(',').map(n => n.trim()));
  const width = 48;
  const height = 24;
  const colors = CATEGORY_COLORS[color];

  const layerSpacing = width / (layers.length + 1);
  const nodes: { x: number; y: number }[] = [];
  const edges: { from: number; to: number }[] = [];

  let nodeIndex = 0;
  const layerStarts: number[] = [];

  layers.forEach((layer, li) => {
    layerStarts.push(nodeIndex);
    const x = layerSpacing * (li + 1);
    layer.forEach((_, ni) => {
      const ySpacing = height / (layer.length + 1);
      nodes.push({ x, y: ySpacing * (ni + 1) });
      nodeIndex++;
    });
  });

  for (let li = 0; li < layers.length - 1; li++) {
    const fStart = layerStarts[li];
    const fEnd = fStart + layers[li].length;
    const tStart = layerStarts[li + 1];
    const tEnd = tStart + layers[li + 1].length;
    for (let fi = fStart; fi < fEnd; fi++) {
      for (let ti = tStart; ti < tEnd; ti++) {
        edges.push({ from: fi, to: ti });
      }
    }
  }

  return (
    <svg width={width} height={height} className="shrink-0" aria-hidden="true">
      {edges.map((e, i) => (
        <line key={i} x1={nodes[e.from].x} y1={nodes[e.from].y}
              x2={nodes[e.to].x} y2={nodes[e.to].y}
              className={colors.text} stroke="currentColor" strokeWidth="1" opacity="0.4" />
      ))}
      {nodes.map((n, i) => (
        <circle key={i} cx={n.x} cy={n.y} r="2.5"
                className={colors.text} fill="currentColor" opacity="0.8" />
      ))}
    </svg>
  );
}

// --- PatternCard ---

function PatternCard({
  pattern,
  color,
  onSelect,
}: {
  pattern: Pattern;
  color: string;
  onSelect: (p: Pattern) => void;
}) {
  const colors = CATEGORY_COLORS[color];
  const dsl = pattern.dsl || pattern.example || '';
  const nodeCount = pattern.node_count ?? new Set(
    dsl.split(/->|,/).map(s => s.trim()).filter(Boolean)
  ).size;
  const isPopular = POPULAR_PATTERNS.has(pattern.name);

  return (
    <button
      onClick={() => onSelect(pattern)}
      title={dsl}
      data-testid={`scaffold-pattern-${pattern.name}`}
      className={`group text-left border border-[#252528] ${colors.border} border-l-2 rounded-lg p-4
        bg-[#1a1a1d]/50 hover:bg-[#1a1a1d] hover:border-[#333338]
        transition-all duration-150`}
    >
      {/* Header: name + node count + popular badge */}
      <div className="flex items-center gap-2 mb-2">
        <h4 className="font-medium text-[#f0f0f0] text-sm flex-1 truncate">
          {pattern.name}
        </h4>
        {isPopular && (
          <span className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/15 text-amber-400 border border-amber-500/20">
            <Star size={10} />
            Popular
          </span>
        )}
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${colors.bg} ${colors.text}`}>
          {nodeCount}n
        </span>
      </div>

      {/* Mini graph */}
      <div className="flex items-center justify-center py-2 mb-2 rounded bg-[#131315]/50">
        <MiniGraph dsl={dsl} color={color} />
      </div>

      {/* Description + use case */}
      <p className="text-xs text-[#80808a] line-clamp-2 leading-relaxed">
        {pattern.description}
      </p>
      {pattern.use_case && (
        <p className="text-[10px] text-[#4a4a52] mt-1.5 italic line-clamp-1">
          {pattern.use_case}
        </p>
      )}

      {/* Tags */}
      {pattern.tags && pattern.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {pattern.tags.map(tag => (
            <span key={tag} className="px-1.5 py-0.5 rounded text-[10px] bg-[#252528]/50 text-[#4a4a52]">
              {tag}
            </span>
          ))}
        </div>
      )}
    </button>
  );
}

export default function Scaffold() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>('dsl');
  const [expression, setExpression] = useState('');
  const [generatedYaml, setGeneratedYaml] = useState('');
  const [copied, setCopied] = useState(false);

  const { data: patternsData, isLoading: loadingPatterns } = usePatterns();
  const scaffold = useScaffold();

  const handleGenerate = () => {
    if (!expression.trim()) return;
    scaffold.mutate(
      { mode: 'dsl', expression: expression.trim() },
      {
        onSuccess: (result) => {
          setGeneratedYaml(result.yaml);
        },
      },
    );
  };

  const handleSelectPattern = (pattern: Pattern) => {
    if (
      (expression.trim() || generatedYaml.trim()) &&
      !window.confirm('This will replace your current DSL expression and generated YAML. Continue?')
    ) {
      return;
    }
    setExpression(pattern.dsl || pattern.example || '');
    scaffold.mutate(
      { mode: 'template', template_name: pattern.name },
      {
        onSuccess: (result) => {
          setGeneratedYaml(result.yaml);
          setMode('dsl');
        },
      },
    );
  };

  const handleOpenInEditor = (yaml: string) => {
    navigate('/editor', { state: { initialContent: yaml } });
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <PageShell className="max-w-5xl">
      <Breadcrumb items={[{ label: 'Workflows', href: '/editor' }, { label: 'Create Workflow' }]} className="mb-4" />

      <PageHeader title="Create Workflow" />

      <div className="mt-6 flex flex-col gap-6">
        {/* Mode tabs */}
        <div className="flex gap-1 border border-[#252528] rounded-lg bg-[#1a1a1d]/50 p-1 w-fit">
          {TAB_CONFIG.map(({ mode: m, label, icon: Icon }) => (
            <button
              key={m}
              data-testid={`scaffold-tab-${m}`}
              onClick={() => setMode(m)}
              className={`flex items-center gap-2 px-4 py-2 text-sm rounded-md transition-colors ${
                mode === m
                  ? 'bg-amber-500 text-black'
                  : 'text-[#80808a] hover:text-[#f0f0f0] hover:bg-[#252528]/50'
              }`}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </div>

        {/* DSL Mode */}
        {mode === 'dsl' && (
          <div className="space-y-4">
            <div className="border border-[#252528] rounded-card bg-[#1a1a1d]/50 p-4 space-y-3">
              <label className="block text-sm text-[#80808a]">
                DSL Expression
              </label>
              <div className="flex gap-2">
                <Input
                  type="text"
                  value={expression}
                  onChange={(e) => setExpression(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
                  placeholder='e.g. "A -> B, C -> D"'
                  className="flex-1 font-mono"
                  data-testid="scaffold-dsl-input"
                />
                <Button
                  onClick={handleGenerate}
                  disabled={!expression.trim() || scaffold.isPending}
                  size="sm"
                  className="bg-amber-500 hover:bg-amber-600"
                  data-testid="scaffold-generate-btn"
                >
                  {scaffold.isPending ? (
                    'Generating...'
                  ) : (
                    <>
                      <ArrowRight size={16} className="mr-1.5" />
                      Generate
                    </>
                  )}
                </Button>
              </div>
              <p className="text-xs text-[#4a4a52]">
                Use arrows to define flow: "A -&gt; B" for sequential, "A -&gt; B, C" for parallel branching.
              </p>
            </div>

            {scaffold.error && (
              <div data-testid="scaffold-error" className="rounded-md bg-red-900/30 border border-red-700/50 p-3 text-sm text-red-300">
                {scaffold.error.message}
              </div>
            )}

            {generatedYaml && (
              <div className="border border-[#252528] rounded-card overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 border-b border-[#252528]">
                  <span className="text-sm font-medium text-[#80808a]">
                    Generated YAML
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={() => handleCopy(generatedYaml)}
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      data-testid="scaffold-copy-btn"
                    >
                      {copied ? <Check size={12} className="mr-1" /> : <Copy size={12} className="mr-1" />}
                      {copied ? 'Copied' : 'Copy'}
                    </Button>
                    <Button
                      onClick={() => handleOpenInEditor(generatedYaml)}
                      size="sm"
                      className="h-7 text-xs"
                      data-testid="scaffold-open-editor-btn"
                    >
                      Open in Editor
                    </Button>
                  </div>
                </div>
                <pre data-testid="scaffold-yaml-output" className="p-4 text-xs text-[#80808a] whitespace-pre-wrap font-mono overflow-x-auto max-h-96 overflow-y-auto bg-[#131315]">
                  {generatedYaml}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* Template Mode */}
        {mode === 'template' && (
          <div className="space-y-8">
            {loadingPatterns ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <div key={i} className="h-36 bg-[#1a1a1d] rounded-lg animate-pulse" />
                ))}
              </div>
            ) : !patternsData?.patterns || patternsData.patterns.length === 0 ? (
              <div className="border border-[#252528] rounded-card bg-[#1a1a1d]/50 p-8 text-center">
                <p className="text-[#80808a]">No patterns available.</p>
              </div>
            ) : (
              CATEGORY_ORDER.map((catId) => {
                const meta = CATEGORY_META[catId];
                if (!meta) return null;
                const { label, description, icon: Icon, color } = meta;
                const items = patternsData.patterns.filter(p => p.category === catId || (!p.category && catId === 'core'));
                if (items.length === 0) return null;
                return (
                  <div key={catId}>
                    <div className="flex items-center gap-2 mb-3">
                      <Icon size={16} className={CATEGORY_COLORS[color].text} />
                      <h3 className="text-sm font-medium text-[#80808a]">{label}</h3>
                      <span className="text-xs text-[#4a4a52]">&mdash; {description}</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {items.map(pattern => (
                        <PatternCard
                          key={pattern.name}
                          pattern={pattern}
                          color={color}
                          onSelect={handleSelectPattern}
                        />
                      ))}
                    </div>
                  </div>
                );
              })
            )}

            {scaffold.isPending && (
              <p className="text-sm text-[#80808a]">Generating workflow...</p>
            )}
            {scaffold.error && (
              <div className="rounded-md bg-red-900/30 border border-red-700/50 p-3 text-sm text-red-300">
                {scaffold.error.message}
              </div>
            )}
          </div>
        )}

        {/* Blank Mode */}
        {mode === 'blank' && (
          <div className="space-y-4">
            <div className="border border-[#252528] rounded-card overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2 border-b border-[#252528]">
                <span className="text-sm font-medium text-[#80808a]">
                  Starter Template
                </span>
                <Button
                  onClick={() => handleOpenInEditor(BLANK_YAML)}
                  size="sm"
                  className="h-7 text-xs"
                  data-testid="scaffold-blank-open-editor-btn"
                >
                  Open in Editor
                </Button>
              </div>
              <pre className="p-4 text-xs text-[#80808a] whitespace-pre-wrap font-mono overflow-x-auto bg-[#131315]">
                {BLANK_YAML}
              </pre>
            </div>
          </div>
        )}
      </div>
    </PageShell>
  );
}
