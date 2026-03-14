import { memo, useState, useCallback } from 'react';
import { Handle, Position, useReactFlow, type NodeProps } from 'reactflow';
import { Bot, Monitor, ShieldCheck, MessageSquare, Globe, Eye, X, Trash2 } from 'lucide-react';
import { ModelSelect } from './ModelSelect';

const ICONS: Record<string, React.ElementType> = {
  llm: Bot, local: Monitor, 'human-approve': ShieldCheck,
  'human-input': MessageSquare, 'human-output': Eye, a2a: Globe,
};

interface EditableNodeData {
  label: string;
  nodeType: string;
  agent: string;
  config: Record<string, unknown>;
  color: string;
}

function EditableNodeInner({ data, id }: NodeProps<EditableNodeData>) {
  const { deleteElements } = useReactFlow();
  const [expanded, setExpanded] = useState(false);
  const [label, setLabel] = useState(data.label);
  const [agent, setAgent] = useState(data.agent);
  const [config, setConfig] = useState<Record<string, unknown>>(data.config || {});

  const handleDelete = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    deleteElements({ nodes: [{ id }] });
  }, [deleteElements, id]);

  const Icon = ICONS[data.nodeType] || Bot;
  const model = agent.includes('://') ? agent.split('://')[1] : agent;

  const notifyChange = useCallback(() => {
    window.dispatchEvent(new CustomEvent('binex:node-data-change'));
  }, []);

  const updateConfig = useCallback((key: string, value: unknown) => {
    setConfig((prev) => {
      const next = { ...prev, [key]: value };
      data.config = next;
      return next;
    });
    notifyChange();
  }, [data, notifyChange]);

  const updateAgent = useCallback((newAgent: string) => {
    setAgent(newAgent);
    data.agent = newAgent;
    notifyChange();
  }, [data, notifyChange]);

  const updateLabel = useCallback((newLabel: string) => {
    setLabel(newLabel);
    data.label = newLabel;
  }, [data]);

  if (!expanded) {
    return (
      <div
        className="group bg-slate-800 rounded-lg border-2 px-4 py-2.5 shadow-lg shadow-black/20 min-w-[180px] max-w-[220px] cursor-pointer hover:brightness-110 transition-all relative"
        style={{ borderColor: data.color }}
        onClick={() => setExpanded(true)}
      >
        <Handle type="target" position={Position.Top} className="!bg-slate-500 !border-slate-400" />
        <button
          onClick={handleDelete}
          className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-red-600 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500"
          title="Delete node"
        >
          <Trash2 size={10} />
        </button>
        <div className="flex items-center gap-2">
          <Icon size={16} style={{ color: data.color }} className="shrink-0" />
          <span className="text-sm font-medium text-slate-100 truncate">{label}</span>
        </div>
        <Handle type="source" position={Position.Bottom} className="!bg-slate-500 !border-slate-400" />
      </div>
    );
  }

  return (
    <div
      className="bg-slate-800 rounded-lg border-2 shadow-xl shadow-black/30 w-[280px] nowheel"
      style={{ borderColor: data.color }}
    >
      <Handle type="target" position={Position.Top} className="!bg-slate-500 !border-slate-400" />

      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <Icon size={14} style={{ color: data.color }} />
          <input
            value={label}
            onChange={(e) => updateLabel(e.target.value)}
            className="bg-transparent text-sm font-medium text-slate-100 border-none outline-none w-36"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
        <div className="flex items-center gap-1">
          <button onClick={handleDelete} className="text-red-500 hover:text-red-400" title="Delete node">
            <Trash2 size={13} />
          </button>
          <button onClick={(e) => { e.stopPropagation(); setExpanded(false); }} className="text-slate-500 hover:text-slate-300">
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Fields */}
      <div className="p-3 space-y-2.5 text-xs">
        {data.nodeType === 'llm' && (
          <>
            <div>
              <label className="text-slate-400 block mb-0.5">Model</label>
              <ModelSelect value={model} onChange={(m) => updateAgent(`llm://${m}`)} />
            </div>
            <div>
              <label className="text-slate-400 block mb-0.5">Max Tokens</label>
              <input type="number" value={(config.max_tokens as number) || 4096}
                onChange={(e) => updateConfig('max_tokens', parseInt(e.target.value) || 4096)}
                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200"
                onClick={(e) => e.stopPropagation()} />
            </div>
            <div>
              <label className="text-slate-400 block mb-0.5">Temperature: {(config.temperature as number) ?? 0.7}</label>
              <input type="range" min="0" max="2" step="0.1" value={(config.temperature as number) ?? 0.7}
                onChange={(e) => updateConfig('temperature', parseFloat(e.target.value))}
                className="w-full accent-blue-500" />
            </div>
            <div>
              <label className="text-slate-400 block mb-0.5">System Prompt</label>
              <select
                value=""
                onChange={(e) => {
                  if (e.target.value) {
                    fetch(`/api/v1/prompts/templates/${e.target.value}`)
                      .then(r => r.json())
                      .then(data => {
                        if (data.content) updateConfig('system_prompt', data.content);
                      });
                  }
                }}
                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200 mb-1"
                onClick={(e) => e.stopPropagation()}
              >
                <option value="">Choose built-in prompt...</option>
                <optgroup label="⭐ Workflow Roles">
                  <option value="wf-planner">Planner — break goal into steps</option>
                  <option value="gen-researcher">Researcher — investigate & report</option>
                  <option value="wf-analyzer">Analyzer — find patterns & insights</option>
                  <option value="gen-draft-writer">Writer — produce first draft</option>
                  <option value="gen-content-reviewer">Reviewer — evaluate & give feedback</option>
                  <option value="sup-summarizer-brief">Summarizer — distill to essentials</option>
                </optgroup>
                <optgroup label="Development">
                  <option value="dev-coder">Coder</option>
                  <option value="dev-code-reviewer-strict">Code Reviewer (Strict)</option>
                  <option value="dev-code-reviewer-mentor">Code Reviewer (Mentor)</option>
                  <option value="dev-test-writer">Test Writer</option>
                  <option value="dev-docs-generator">Docs Generator</option>
                  <option value="dev-refactorer">Refactorer</option>
                  <option value="dev-bug-reproducer">Bug Reproducer</option>
                  <option value="dev-security-auditor-strict">Security Auditor</option>
                </optgroup>
                <optgroup label="Content">
                  <option value="cnt-content-drafter-formal">Content Drafter (Formal)</option>
                  <option value="cnt-content-drafter-casual">Content Drafter (Casual)</option>
                  <option value="cnt-seo-optimizer">SEO Optimizer</option>
                  <option value="cnt-outline-writer">Outline Writer</option>
                </optgroup>
                <optgroup label="Data">
                  <option value="dat-data-validator">Data Validator</option>
                  <option value="dat-data-normalizer">Data Normalizer</option>
                  <option value="dat-quality-reporter">Quality Reporter</option>
                </optgroup>
                <optgroup label="Business">
                  <option value="biz-executive-summarizer-brief">Executive Summary (Brief)</option>
                  <option value="biz-executive-summarizer-detailed">Executive Summary (Detailed)</option>
                  <option value="biz-swot-writer">SWOT Analysis</option>
                  <option value="biz-recommender">Recommender</option>
                </optgroup>
                <optgroup label="General">
                  <option value="gen-researcher">Researcher</option>
                  <option value="gen-draft-writer">Draft Writer</option>
                  <option value="gen-content-reviewer">Content Reviewer</option>
                  <option value="gen-data-processor">Data Processor</option>
                </optgroup>
                <optgroup label="Support">
                  <option value="sup-response-generator">Response Generator</option>
                  <option value="sup-translator-adaptive">Translator (Adaptive)</option>
                  <option value="sup-summarizer-brief">Summarizer (Brief)</option>
                </optgroup>
              </select>
              <textarea value={(config.system_prompt as string) || ''}
                onChange={(e) => updateConfig('system_prompt', e.target.value)}
                placeholder="Or write your own prompt..."
                rows={3}
                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200 resize-none"
                onClick={(e) => e.stopPropagation()} />
            </div>
            <div>
              <label className="text-slate-400 block mb-0.5">Budget Limit ($)</label>
              <input type="number" step="0.01" value={(config.budget_limit as number) || ''}
                onChange={(e) => updateConfig('budget_limit', parseFloat(e.target.value) || undefined)}
                placeholder="No limit"
                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200"
                onClick={(e) => e.stopPropagation()} />
            </div>
          </>
        )}

        {data.nodeType === 'local' && (
          <div>
            <label className="text-slate-400 block mb-0.5">Module Path</label>
            <input value={agent.replace('local://', '')}
              onChange={(e) => updateAgent(`local://${e.target.value}`)}
              placeholder="my_module.my_function"
              className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200 font-mono"
              onClick={(e) => e.stopPropagation()} />
          </div>
        )}

        {data.nodeType === 'human-output' && (
          <div>
            <label className="text-slate-400 block mb-0.5">Display Label</label>
            <input value={(config.display_label as string) || ''}
              onChange={(e) => updateConfig('display_label', e.target.value)}
              placeholder="Final Result"
              className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200"
              onClick={(e) => e.stopPropagation()} />
            <p className="text-slate-500 mt-1">Shows the output of connected nodes to the user when workflow completes.</p>
          </div>
        )}

        {(data.nodeType === 'human-approve' || data.nodeType === 'human-input') && (
          <div>
            <label className="text-slate-400 block mb-0.5">Prompt Message</label>
            <textarea value={(config.prompt_message as string) || ''}
              onChange={(e) => updateConfig('prompt_message', e.target.value)}
              placeholder={data.nodeType === 'human-approve' ? 'Please review and approve...' : 'Please provide input...'}
              rows={2}
              className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200 resize-none"
              onClick={(e) => e.stopPropagation()} />
          </div>
        )}

        {data.nodeType === 'a2a' && (
          <>
            <div>
              <label className="text-slate-400 block mb-0.5">Host:Port</label>
              <input value={agent.replace('a2a://', '')}
                onChange={(e) => updateAgent(`a2a://${e.target.value}`)}
                placeholder="localhost:8001"
                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200 font-mono"
                onClick={(e) => e.stopPropagation()} />
            </div>
            <div>
              <label className="text-slate-400 block mb-0.5">Skill</label>
              <input value={(config.skill as string) || ''}
                onChange={(e) => updateConfig('skill', e.target.value)}
                placeholder="summarize"
                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200"
                onClick={(e) => e.stopPropagation()} />
            </div>
          </>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-slate-500 !border-slate-400" />
    </div>
  );
}

export const EditableNode = memo(EditableNodeInner);
