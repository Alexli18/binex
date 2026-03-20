import { memo, useState, useCallback } from 'react';
import { Handle, Position, useReactFlow, type NodeProps } from 'reactflow';
import { Bot, Monitor, ShieldCheck, MessageSquare, Globe, Eye, X, Trash2, BookOpen, Wrench, Terminal } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { ModelSelect } from './ModelSelect';
import { CollapsibleSection } from './CollapsibleSection';
import { ToolChip } from './ToolChip';
import { ToolPickerPopover } from './ToolPickerPopover';
import { PromptLibraryPanel } from '../../pages/PromptLibrary';
import { CaoNodePanel } from './CaoNodePanel';

const ICONS: Record<string, React.ElementType> = {
  llm: Bot, local: Monitor, 'human-approve': ShieldCheck,
  'human-input': MessageSquare, 'human-output': Eye, a2a: Globe,
  cao: Terminal,
};

const TYPE_LABELS: Record<string, string> = {
  llm: 'LLM Agent', local: 'Script', 'human-approve': 'Approval',
  'human-input': 'Input', 'human-output': 'Output', a2a: 'A2A Agent',
  cao: 'CAO Agent',
};

export interface EditableNodeData {
  label: string;
  nodeType: string;
  agent: string;
  config: Record<string, unknown>;
  color: string;
  tools?: string[];
}

function EditableNodeInner({ data, id, selected }: NodeProps<EditableNodeData>) {
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
        className={`group rounded-lg border shadow-lg shadow-black/20 min-w-[180px] max-w-[220px] cursor-pointer hover:shadow-xl transition-all duration-150 relative overflow-hidden animate-node-appear ${selected ? 'border-blue-500/60 ring-2 ring-blue-500/20' : 'border-slate-700/60 hover:border-slate-600'}`}
        style={{ backgroundColor: `${data.color}08` }}
        onClick={() => setExpanded(true)}
      >
        {/* Color accent strip */}
        <div className="h-[3px] w-full" style={{ backgroundColor: data.color }} />
        <Handle type="target" position={Position.Top} className="!w-2.5 !h-2.5 !border-2 !border-slate-700 !bg-slate-400 hover:!bg-blue-400 hover:!border-blue-500 transition-colors" />
        <button
          onClick={handleDelete}
          className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-red-600 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500 z-10"
          title="Delete node"
        >
          <Trash2 size={10} />
        </button>
        <div className="px-3 py-2.5">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-md flex items-center justify-center shrink-0" style={{ backgroundColor: `${data.color}20` }}>
              <Icon size={15} style={{ color: data.color }} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-slate-100 truncate leading-tight">{label}</div>
              <div className="text-[10px] text-slate-500 leading-tight mt-0.5">{TYPE_LABELS[data.nodeType] || data.nodeType}</div>
            </div>
            {tools.length > 0 && (
              <span className="flex items-center gap-0.5 text-[9px] text-blue-400 bg-blue-500/10 px-1 py-0.5 rounded shrink-0">
                <Wrench size={9} />
                {tools.length}
              </span>
            )}
          </div>
        </div>
        <Handle type="source" position={Position.Bottom} className="!w-2.5 !h-2.5 !border-2 !border-slate-700 !bg-slate-400 hover:!bg-blue-400 hover:!border-blue-500 transition-colors" />
      </div>
    );
  }

  // Expanded view
  return (
    <div
      className={`rounded-lg border shadow-xl shadow-black/30 w-[280px] nowheel overflow-hidden ${selected ? 'border-blue-500/60 ring-2 ring-blue-500/20' : 'border-slate-700/60'}`}
      style={{ backgroundColor: `${data.color}08` }}
    >
      {/* Color accent strip */}
      <div className="h-[3px] w-full" style={{ backgroundColor: data.color }} />
      <Handle type="target" position={Position.Top} className="!w-2.5 !h-2.5 !border-2 !border-slate-700 !bg-slate-400 hover:!bg-blue-400 hover:!border-blue-500 transition-colors" />

      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-700/50">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <div className="w-7 h-7 rounded-md flex items-center justify-center shrink-0" style={{ backgroundColor: `${data.color}20` }}>
            <Icon size={15} style={{ color: data.color }} />
          </div>
          <div className="min-w-0 flex-1">
            <input
              value={label}
              onChange={(e) => updateLabel(e.target.value)}
              className="bg-transparent text-sm font-medium text-slate-100 border-none outline-none w-full"
              onClick={(e) => e.stopPropagation()}
            />
            <div className="text-[10px] text-slate-500 leading-tight">{TYPE_LABELS[data.nodeType] || data.nodeType}</div>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0 ml-1">
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
                <p className="text-slate-600 mt-0.5">Maximum response length</p>
              </div>
              <div>
                <label className="text-slate-400 block mb-0.5">
                  Temperature: {(config.temperature as number) ?? 0.7}
                  <span className="ml-1.5 text-slate-600 font-normal normal-case tracking-normal">
                    {((config.temperature as number) ?? 0.7) <= 0.3 ? '(precise)' : ((config.temperature as number) ?? 0.7) >= 1.2 ? '(creative)' : '(balanced)'}
                  </span>
                </label>
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
                <p className="text-slate-600 mt-0.5">Stop this node if cost exceeds limit</p>
              </div>
            </CollapsibleSection>
          </>
        )}

        {data.nodeType === 'local' && (
          <CollapsibleSection title="Configuration" defaultOpen>
            <div>
              <label className="text-slate-400 block mb-0.5">Module Path</label>
              <Input value={agent.replace('local://', '')}
                onChange={(e) => updateAgent(`local://${e.target.value}`)}
                placeholder="my_module.my_function"
                className="h-7 bg-slate-700 border-slate-600 text-slate-200 font-mono"
                onClick={(e) => e.stopPropagation()} />
              <p className="text-slate-600 mt-0.5">Python module.function to execute</p>
            </div>
          </CollapsibleSection>
        )}

        {data.nodeType === 'human-output' && (
          <CollapsibleSection title="Configuration" defaultOpen>
            <div>
              <label className="text-slate-400 block mb-0.5">Display Label</label>
              <Input value={(config.display_label as string) || ''}
                onChange={(e) => updateConfig('display_label', e.target.value)}
                placeholder="Final Result"
                className="h-7 bg-slate-700 border-slate-600 text-slate-200"
                onClick={(e) => e.stopPropagation()} />
              <p className="text-slate-600 mt-0.5">Shows output to user when workflow completes</p>
            </div>
          </CollapsibleSection>
        )}

        {(data.nodeType === 'human-approve' || data.nodeType === 'human-input') && (
          <CollapsibleSection title="Configuration" defaultOpen>
            <div>
              <label className="text-slate-400 block mb-0.5">Prompt Message</label>
              <textarea value={(config.prompt_message as string) || ''}
                onChange={(e) => updateConfig('prompt_message', e.target.value)}
                placeholder={data.nodeType === 'human-approve' ? 'Please review and approve...' : 'Please provide input...'}
                rows={2}
                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200 resize-none"
                onClick={(e) => e.stopPropagation()} />
              <p className="text-slate-600 mt-0.5">{data.nodeType === 'human-approve' ? 'Shown when asking for approval' : 'Shown when asking for input'}</p>
            </div>
          </CollapsibleSection>
        )}

        {data.nodeType === 'a2a' && (
          <CollapsibleSection title="Connection" defaultOpen>
            <div>
              <label className="text-slate-400 block mb-0.5">Endpoint</label>
              <Input value={agent.replace('a2a://', '')}
                onChange={(e) => updateAgent(`a2a://${e.target.value}`)}
                placeholder="localhost:8001"
                className="h-7 bg-slate-700 border-slate-600 text-slate-200 font-mono"
                onClick={(e) => e.stopPropagation()} />
              <p className="text-slate-600 mt-0.5">Remote A2A agent host:port</p>
            </div>
            <div>
              <label className="text-slate-400 block mb-0.5">Skill</label>
              <Input value={(config.skill as string) || ''}
                onChange={(e) => updateConfig('skill', e.target.value)}
                placeholder="summarize"
                className="h-7 bg-slate-700 border-slate-600 text-slate-200"
                onClick={(e) => e.stopPropagation()} />
              <p className="text-slate-600 mt-0.5">Agent skill to invoke</p>
            </div>
          </CollapsibleSection>
        )}

        {data.nodeType === 'cao' && (
          <CaoNodePanel
            agent={agent}
            config={config}
            onAgentChange={updateAgent}
            onConfigChange={updateConfig}
          />
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="!w-2.5 !h-2.5 !border-2 !border-slate-700 !bg-slate-400 hover:!bg-blue-400 hover:!border-blue-500 transition-colors" />

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
