import { memo, useState, useCallback } from 'react';
import { Handle, Position, useReactFlow, type NodeProps } from 'reactflow';
import { Bot, Monitor, ShieldCheck, MessageSquare, Globe, Eye, X, Trash2, BookOpen, Wrench } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { ModelSelect } from './ModelSelect';
import { CollapsibleSection } from './CollapsibleSection';
import { ToolChip } from './ToolChip';
import { ToolPickerPopover } from './ToolPickerPopover';
import { PromptLibraryPanel } from '../../pages/PromptLibrary';

const ICONS: Record<string, React.ElementType> = {
  llm: Bot, local: Monitor, 'human-approve': ShieldCheck,
  'human-input': MessageSquare, 'human-output': Eye, a2a: Globe,
};

export interface EditableNodeData {
  label: string;
  nodeType: string;
  agent: string;
  config: Record<string, unknown>;
  color: string;
  tools?: string[];
  loopRole?: 'entry' | 'exit' | 'entry+exit' | null;
}

function EditableNodeInner({ data, id }: NodeProps<EditableNodeData>) {
  const { deleteElements } = useReactFlow();
  const [expanded, setExpanded] = useState(false);
  const [label, setLabel] = useState(data.label);
  const [agent, setAgent] = useState(data.agent);
  const [config, setConfig] = useState<Record<string, unknown>>(data.config || {});
  const [tools, setTools] = useState<string[]>(data.tools || []);
  const [promptPanelOpen, setPromptPanelOpen] = useState(false);

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

  const toggleTool = useCallback((uri: string) => {
    setTools((prev) => {
      const next = prev.includes(uri) ? prev.filter((t) => t !== uri) : [...prev, uri];
      data.tools = next;
      return next;
    });
    notifyChange();
  }, [data, notifyChange]);

  const removeTool = useCallback((uri: string) => {
    setTools((prev) => {
      const next = prev.filter((t) => t !== uri);
      data.tools = next;
      return next;
    });
    notifyChange();
  }, [data, notifyChange]);

  // Collapsed view
  if (!expanded) {
    return (
      <div
        className="group bg-slate-800 rounded-lg border-2 px-4 py-2.5 shadow-lg shadow-black/20 min-w-[180px] max-w-[220px] cursor-pointer hover:brightness-110 transition-all relative"
        style={{ borderColor: data.color }}
        onClick={() => setExpanded(true)}
      >
        <Handle type="target" position={Position.Top} className="!bg-slate-500 !border-slate-400" />
        {data.loopRole && (
          <div className={cn(
            'absolute -top-2 text-[8px] font-bold tracking-wide uppercase',
            'px-1.5 py-0.5 rounded-full',
            'pointer-events-none select-none',
            'shadow-sm',
            data.loopRole === 'entry' && '-left-2 bg-blue-600/90 text-blue-100',
            data.loopRole === 'exit' && '-right-8 bg-emerald-600/90 text-emerald-100',
            data.loopRole === 'entry+exit' && '-left-2 bg-teal-600/90 text-teal-100',
          )}>
            {data.loopRole === 'entry' && '\u25B8 in'}
            {data.loopRole === 'exit' && 'out \u25C2'}
            {data.loopRole === 'entry+exit' && 'in/out'}
          </div>
        )}
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
          {tools.length > 0 && (
            <span className="flex items-center gap-0.5 text-[9px] text-blue-400 bg-blue-500/10 px-1 py-0.5 rounded">
              <Wrench size={9} />
              {tools.length}
            </span>
          )}
        </div>
        <Handle type="source" position={Position.Bottom} className="!bg-slate-500 !border-slate-400" />
      </div>
    );
  }

  // Expanded view
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

      {/* Sections */}
      <div className="text-xs">
        {data.nodeType === 'llm' && (
          <>
            {/* Model Section */}
            <CollapsibleSection title="Model" defaultOpen>
              <div>
                <label className="text-slate-400 block mb-0.5">Model</label>
                <ModelSelect value={model} onChange={(m) => updateAgent(`llm://${m}`)} />
              </div>
              <div>
                <label className="text-slate-400 block mb-0.5">Max Tokens</label>
                <Input type="number" value={(config.max_tokens as number) || 4096}
                  onChange={(e) => updateConfig('max_tokens', parseInt(e.target.value) || 4096)}
                  className="h-7 bg-slate-700 border-slate-600 text-slate-200"
                  onClick={(e) => e.stopPropagation()} />
              </div>
              <div>
                <label className="text-slate-400 block mb-0.5">Temperature: {(config.temperature as number) ?? 0.7}</label>
                <input type="range" min="0" max="2" step="0.1" value={(config.temperature as number) ?? 0.7}
                  onChange={(e) => updateConfig('temperature', parseFloat(e.target.value))}
                  className="w-full accent-blue-500" />
              </div>
            </CollapsibleSection>

            {/* Prompt Section */}
            <CollapsibleSection title="Prompt" defaultOpen>
              <div>
                <div className="flex items-center justify-between mb-0.5">
                  <label className="text-slate-400">System Prompt</label>
                  <button
                    onClick={(e) => { e.stopPropagation(); setPromptPanelOpen(true); }}
                    className="flex items-center gap-1 text-blue-400 hover:text-blue-300 transition-colors"
                    title="Browse prompt library"
                  >
                    <BookOpen size={11} />
                    <span className="text-[10px]">Browse</span>
                  </button>
                </div>
                <textarea value={(config.system_prompt as string) || ''}
                  onChange={(e) => updateConfig('system_prompt', e.target.value)}
                  placeholder="Write your prompt or click Browse to pick one..."
                  rows={4}
                  className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200 resize-none"
                  onClick={(e) => e.stopPropagation()} />
              </div>
            </CollapsibleSection>

            {/* Tools Section */}
            <CollapsibleSection
              title="Tools"
              badge={tools.length > 0 ? (
                <span className="text-[9px] bg-blue-500/15 text-blue-400 px-1.5 py-0.5 rounded-full font-medium">
                  {tools.length}
                </span>
              ) : undefined}
            >
              {tools.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-1.5">
                  {tools.map((uri) => (
                    <ToolChip key={uri} uri={uri} onRemove={() => removeTool(uri)} />
                  ))}
                </div>
              )}
              <div className="relative">
                <ToolPickerPopover selectedTools={tools} onToggleTool={toggleTool} />
              </div>
            </CollapsibleSection>

            {/* Advanced Section */}
            <CollapsibleSection title="Advanced">
              <div>
                <label className="text-slate-400 block mb-0.5">Budget Limit ($)</label>
                <Input type="number" step="0.01" value={(config.budget_limit as number) || ''}
                  onChange={(e) => updateConfig('budget_limit', parseFloat(e.target.value) || undefined)}
                  placeholder="No limit"
                  className="h-7 bg-slate-700 border-slate-600 text-slate-200"
                  onClick={(e) => e.stopPropagation()} />
              </div>
            </CollapsibleSection>
          </>
        )}

        {data.nodeType === 'local' && (
          <div className="p-3 space-y-2.5">
            <div>
              <label className="text-slate-400 block mb-0.5">Module Path</label>
              <Input value={agent.replace('local://', '')}
                onChange={(e) => updateAgent(`local://${e.target.value}`)}
                placeholder="my_module.my_function"
                className="h-7 bg-slate-700 border-slate-600 text-slate-200 font-mono"
                onClick={(e) => e.stopPropagation()} />
            </div>
          </div>
        )}

        {data.nodeType === 'human-output' && (
          <div className="p-3 space-y-2.5">
            <div>
              <label className="text-slate-400 block mb-0.5">Display Label</label>
              <Input value={(config.display_label as string) || ''}
                onChange={(e) => updateConfig('display_label', e.target.value)}
                placeholder="Final Result"
                className="h-7 bg-slate-700 border-slate-600 text-slate-200"
                onClick={(e) => e.stopPropagation()} />
              <p className="text-slate-500 mt-1">Shows the output of connected nodes to the user when workflow completes.</p>
            </div>
          </div>
        )}

        {(data.nodeType === 'human-approve' || data.nodeType === 'human-input') && (
          <div className="p-3 space-y-2.5">
            <div>
              <label className="text-slate-400 block mb-0.5">Prompt Message</label>
              <textarea value={(config.prompt_message as string) || ''}
                onChange={(e) => updateConfig('prompt_message', e.target.value)}
                placeholder={data.nodeType === 'human-approve' ? 'Please review and approve...' : 'Please provide input...'}
                rows={2}
                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200 resize-none"
                onClick={(e) => e.stopPropagation()} />
            </div>
          </div>
        )}

        {data.nodeType === 'a2a' && (
          <div className="p-3 space-y-2.5">
            <div>
              <label className="text-slate-400 block mb-0.5">Host:Port</label>
              <Input value={agent.replace('a2a://', '')}
                onChange={(e) => updateAgent(`a2a://${e.target.value}`)}
                placeholder="localhost:8001"
                className="h-7 bg-slate-700 border-slate-600 text-slate-200 font-mono"
                onClick={(e) => e.stopPropagation()} />
            </div>
            <div>
              <label className="text-slate-400 block mb-0.5">Skill</label>
              <Input value={(config.skill as string) || ''}
                onChange={(e) => updateConfig('skill', e.target.value)}
                placeholder="summarize"
                className="h-7 bg-slate-700 border-slate-600 text-slate-200"
                onClick={(e) => e.stopPropagation()} />
            </div>
          </div>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-slate-500 !border-slate-400" />

      {promptPanelOpen && (
        <PromptLibraryPanel
          open={promptPanelOpen}
          onClose={() => setPromptPanelOpen(false)}
          onUse={(content) => {
            updateConfig('system_prompt', content);
            setPromptPanelOpen(false);
          }}
        />
      )}
    </div>
  );
}

export const EditableNode = memo(EditableNodeInner);
