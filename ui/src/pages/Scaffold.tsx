import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Wand2, Layout, FileText, ArrowRight, Copy, Check } from 'lucide-react';
import { usePatterns, useScaffold } from '../hooks/useUtilities';
import type { Pattern } from '../hooks/useUtilities';

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

function PatternCard({
  pattern,
  onSelect,
}: {
  pattern: Pattern;
  onSelect: (p: Pattern) => void;
}) {
  return (
    <button
      onClick={() => onSelect(pattern)}
      className="text-left border border-slate-700 rounded-lg p-4 bg-slate-800/50 hover:bg-slate-700/50 hover:border-slate-600 transition-colors"
    >
      <h4 className="font-medium text-slate-200">{pattern.name}</h4>
      <p className="text-xs text-slate-400 mt-1">{pattern.description}</p>
      <p className="text-xs font-mono text-blue-400 mt-2 bg-slate-900 rounded px-2 py-1">
        {pattern.example}
      </p>
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
    setExpression(pattern.example);
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
    <div className="p-6 flex flex-col gap-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Wand2 size={24} className="text-purple-400" />
        <h1 className="text-xl font-bold">Create Workflow</h1>
      </div>

      {/* Mode tabs */}
      <div className="flex gap-1 border border-slate-700 rounded-lg bg-slate-800/50 p-1 w-fit">
        {TAB_CONFIG.map(({ mode: m, label, icon: Icon }) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`flex items-center gap-2 px-4 py-2 text-sm rounded-md transition-colors ${
              mode === m
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
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
          <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-4 space-y-3">
            <label className="block text-sm text-slate-400">
              DSL Expression
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={expression}
                onChange={(e) => setExpression(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
                placeholder='e.g. "A -> B, C -> D"'
                className="flex-1 bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-blue-500 font-mono"
              />
              <button
                onClick={handleGenerate}
                disabled={!expression.trim() || scaffold.isPending}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {scaffold.isPending ? (
                  'Generating...'
                ) : (
                  <>
                    <ArrowRight size={16} />
                    Generate
                  </>
                )}
              </button>
            </div>
            <p className="text-xs text-slate-500">
              Use arrows to define flow: "A -&gt; B" for sequential, "A -&gt; B, C" for parallel branching.
            </p>
          </div>

          {scaffold.error && (
            <div className="rounded-md bg-red-900/30 border border-red-700/50 p-3 text-sm text-red-300">
              {scaffold.error.message}
            </div>
          )}

          {generatedYaml && (
            <div className="border border-slate-700 rounded-lg bg-slate-800/50 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700">
                <span className="text-sm font-medium text-slate-300">
                  Generated YAML
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleCopy(generatedYaml)}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs rounded border border-slate-600 text-slate-300 hover:bg-slate-700 transition-colors"
                  >
                    {copied ? <Check size={12} /> : <Copy size={12} />}
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                  <button
                    onClick={() => handleOpenInEditor(generatedYaml)}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                  >
                    Open in Editor
                  </button>
                </div>
              </div>
              <pre className="p-4 text-xs text-slate-300 whitespace-pre-wrap font-mono overflow-x-auto max-h-96 overflow-y-auto bg-slate-900">
                {generatedYaml}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Template Mode */}
      {mode === 'template' && (
        <div className="space-y-4">
          <p className="text-sm text-slate-400">
            Select a predefined pattern to generate a workflow.
          </p>
          {loadingPatterns ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {[1, 2, 3, 4].map((i) => (
                <div
                  key={i}
                  className="h-28 bg-slate-800 rounded-lg animate-pulse"
                />
              ))}
            </div>
          ) : !patternsData?.patterns || patternsData.patterns.length === 0 ? (
            <div className="border border-slate-700 rounded-lg bg-slate-800/50 p-8 text-center">
              <p className="text-slate-400">No patterns available.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {patternsData.patterns.map((pattern) => (
                <PatternCard
                  key={pattern.name}
                  pattern={pattern}
                  onSelect={handleSelectPattern}
                />
              ))}
            </div>
          )}

          {scaffold.isPending && (
            <p className="text-sm text-slate-400">Generating workflow...</p>
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
          <div className="border border-slate-700 rounded-lg bg-slate-800/50 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700">
              <span className="text-sm font-medium text-slate-300">
                Starter Template
              </span>
              <button
                onClick={() => handleOpenInEditor(BLANK_YAML)}
                className="flex items-center gap-1 px-2.5 py-1 text-xs rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors"
              >
                Open in Editor
              </button>
            </div>
            <pre className="p-4 text-xs text-slate-300 whitespace-pre-wrap font-mono overflow-x-auto bg-slate-900">
              {BLANK_YAML}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
