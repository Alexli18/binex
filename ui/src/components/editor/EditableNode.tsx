import { memo, useState, useCallback } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Bot, Monitor, ShieldCheck, MessageSquare, Globe, X } from 'lucide-react';
import { ModelSelect } from './ModelSelect';

const ICONS: Record<string, React.ElementType> = {
  llm: Bot, local: Monitor, 'human-approve': ShieldCheck,
  'human-input': MessageSquare, a2a: Globe,
};

interface EditableNodeData {
  label: string;
  nodeType: string;
  agent: string;
  config: Record<string, unknown>;
  color: string;
}

function EditableNodeInner({ data }: NodeProps<EditableNodeData>) {
  const [expanded, setExpanded] = useState(false);
  const [label, setLabel] = useState(data.label);
  const [agent, setAgent] = useState(data.agent);
  const [config, setConfig] = useState<Record<string, unknown>>(data.config || {});

  const Icon = ICONS[data.nodeType] || Bot;
  const model = agent.includes('://') ? agent.split('://')[1] : agent;

  const updateConfig = useCallback((key: string, value: unknown) => {
    setConfig((prev) => {
      const next = { ...prev, [key]: value };
      data.config = next;
      return next;
    });
  }, [data]);

  const updateAgent = useCallback((newAgent: string) => {
    setAgent(newAgent);
    data.agent = newAgent;
  }, [data]);

  const updateLabel = useCallback((newLabel: string) => {
    setLabel(newLabel);
    data.label = newLabel;
  }, [data]);

  if (!expanded) {
    return (
      <div
        className="bg-slate-800 rounded-lg border-2 px-4 py-2.5 shadow-lg shadow-black/20 min-w-[180px] max-w-[220px] cursor-pointer hover:brightness-110 transition-all"
        style={{ borderColor: data.color }}
        onClick={() => setExpanded(true)}
      >
        <Handle type="target" position={Position.Top} className="!bg-slate-500 !border-slate-400" />
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
        <button onClick={(e) => { e.stopPropagation(); setExpanded(false); }} className="text-slate-500 hover:text-slate-300">
          <X size={14} />
        </button>
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
              <textarea value={(config.system_prompt as string) || ''}
                onChange={(e) => updateConfig('system_prompt', e.target.value)}
                placeholder="You are a helpful assistant..."
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
