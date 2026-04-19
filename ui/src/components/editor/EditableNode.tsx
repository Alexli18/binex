import { memo, useState, useCallback, useEffect, useRef } from 'react';
import { Handle, Position, useReactFlow, type NodeProps } from 'reactflow';
import { X, Trash2, BookOpen, Wrench, Check } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { ModelSelect } from './ModelSelect';
import { CollapsibleSection } from './CollapsibleSection';
import { ToolChip } from './ToolChip';
import { ToolPickerPopover } from './ToolPickerPopover';
import { PromptLibraryPanel } from '../../pages/PromptLibrary';
import { CaoNodePanel } from './CaoNodePanel';
import { PatternConfig } from './PatternConfig';


const TYPE_LABELS: Record<string, string> = {
  llm: 'LLM', local: 'Script', 'human-approve': 'Approve',
  'human-input': 'Input', 'human-output': 'Output', a2a: 'A2A',
  cao: 'CAO',
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
  const [showSaved, setShowSaved] = useState(false);
  const savedTimer = useRef<ReturnType<typeof setTimeout>>();

  const handleDelete = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    deleteElements({ nodes: [{ id }] });
  }, [deleteElements, id]);

  const model = agent.includes('://') ? agent.split('://')[1] : agent;

  const notifyChange = useCallback(() => {
    window.dispatchEvent(new CustomEvent('binex:node-data-change'));
    setShowSaved(true);
    clearTimeout(savedTimer.current);
    savedTimer.current = setTimeout(() => setShowSaved(false), 1500);
  }, []);

  useEffect(() => () => clearTimeout(savedTimer.current), []);

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

  const handleStyle = "!w-1.5 !h-1.5 !border !border-[#333338] !bg-[#4a4a52] hover:!bg-[#e8a020] hover:!border-[#e8a020] !rounded-none !transition-colors";

  const nodeBase: React.CSSProperties = {
    background: "#1a1a1d",
    border: selected ? `1px solid ${data.color}` : "1px solid #252528",
    borderTop: `2px solid ${data.color}`,
    boxShadow: selected ? `0 0 0 1px ${data.color}22, 0 4px 16px rgba(0,0,0,.5)` : "0 2px 8px rgba(0,0,0,.4)",
    transition: "all .1s",
  };

  // Collapsed view
  if (!expanded) {
    return (
      <div
        style={{ ...nodeBase, width: 160, cursor: "pointer", position: "relative" }}
        className="animate-node-appear"
        onClick={() => setExpanded(true)}
      >
        <Handle type="target" position={Position.Top} className={handleStyle} />
        {/* Type row */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "6px 10px", borderBottom: "1px solid #252528",
        }}>
          <span style={{ fontSize: 9, color: data.color, letterSpacing: ".08em", textTransform: "uppercase" }}>
            {TYPE_LABELS[data.nodeType] || data.nodeType}
          </span>
          {tools.length > 0 && (
            <span style={{ fontSize: 9, color: "#e8a020", background: "rgba(232,160,32,0.12)", padding: "1px 5px", display: "flex", alignItems: "center", gap: 3 }}>
              <Wrench size={8} />
              {tools.length}
            </span>
          )}
        </div>
        {/* Label */}
        <div style={{ padding: "6px 10px", fontSize: 12, color: selected ? "#f0f0f0" : "#80808a", fontWeight: selected ? 600 : 400 }}>
          {label}
        </div>
        <Handle type="source" position={Position.Bottom} className={handleStyle} />
      </div>
    );
  }

  // Expanded view
  return (
    <div style={{ ...nodeBase, width: 260 }} className="nowheel">
      <Handle type="target" position={Position.Top} className={handleStyle} />

      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", gap: 6,
        padding: "6px 10px", borderBottom: "1px solid #252528",
      }}>
        <span style={{ fontSize: 9, color: data.color, letterSpacing: ".08em", textTransform: "uppercase" }}>
          ◼ {TYPE_LABELS[data.nodeType]}
        </span>
        <input
          value={label}
          onChange={(e) => updateLabel(e.target.value)}
          style={{
            background: "transparent", fontSize: 12, fontWeight: 600,
            color: "#f0f0f0", border: "none", outline: "none", minWidth: 0, flex: 1,
            fontFamily: "inherit",
          }}
          onClick={(e) => e.stopPropagation()}
        />
        <button onClick={handleDelete} style={{ background: "none", border: "none", cursor: "pointer", color: "#4a4a52", padding: 2, display: "flex" }}
          onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = "#ef4444")}
          onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = "#4a4a52")}
          title="Delete">
          <Trash2 size={12} />
        </button>
        <button onClick={(e) => { e.stopPropagation(); setExpanded(false); }}
          style={{ background: "none", border: "none", cursor: "pointer", color: "#4a4a52", padding: 2, display: "flex" }}
          onMouseEnter={(e) => ((e.currentTarget as HTMLElement).style.color = "#80808a")}
          onMouseLeave={(e) => ((e.currentTarget as HTMLElement).style.color = "#4a4a52")}>
          <X size={13} />
        </button>
      </div>

      {/* Sections */}
      <div className="text-xs">
        {data.nodeType === 'llm' && (
          <>
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
                <label className="text-slate-400 block mb-0.5">
                  Temperature: {(config.temperature as number) ?? 0.7}
                  <span className="ml-1 text-slate-600 font-normal normal-case tracking-normal">
                    {((config.temperature as number) ?? 0.7) <= 0.3 ? '· precise' : ((config.temperature as number) ?? 0.7) >= 1.2 ? '· creative' : '· balanced'}
                  </span>
                </label>
                <input type="range" min="0" max="2" step="0.1" value={(config.temperature as number) ?? 0.7}
                  onChange={(e) => updateConfig('temperature', parseFloat(e.target.value))}
                  className="w-full accent-amber-500" />
              </div>
            </CollapsibleSection>

            <CollapsibleSection title="Prompt">
              <div>
                <div className="flex items-center justify-between mb-0.5">
                  <label className="text-slate-400">System Prompt</label>
                  <button
                    onClick={(e) => { e.stopPropagation(); setPromptPanelOpen(true); }}
                    className="flex items-center gap-1 transition-colors" style={{ color: "#e8a020" }}
                    title="Browse prompt library"
                  >
                    <BookOpen size={10} />
                    <span className="text-[10px]">Browse</span>
                  </button>
                </div>
                <textarea value={(config.system_prompt as string) || ''}
                  onChange={(e) => updateConfig('system_prompt', e.target.value)}
                  placeholder="System prompt..."
                  rows={3}
                  className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200 resize-none text-xs"
                  onClick={(e) => e.stopPropagation()} />
              </div>
            </CollapsibleSection>

            <CollapsibleSection
              title="Tools"
              badge={tools.length > 0 ? (
                <span className="text-[9px] px-1.5 py-0.5 font-medium" style={{ color: "#e8a020", background: "rgba(232,160,32,0.12)" }}>
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
          <CollapsibleSection title="Config" defaultOpen>
            <div>
              <label className="text-slate-400 block mb-0.5">Module Path</label>
              <Input value={agent.replace('local://', '')}
                onChange={(e) => updateAgent(`local://${e.target.value}`)}
                placeholder="my_module.my_function"
                className="h-7 bg-slate-700 border-slate-600 text-slate-200 font-mono"
                onClick={(e) => e.stopPropagation()} />
            </div>
          </CollapsibleSection>
        )}

        {data.nodeType === 'human-output' && (
          <CollapsibleSection title="Config" defaultOpen>
            <div>
              <label className="text-slate-400 block mb-0.5">Display Label</label>
              <Input value={(config.display_label as string) || ''}
                onChange={(e) => updateConfig('display_label', e.target.value)}
                placeholder="Final Result"
                className="h-7 bg-slate-700 border-slate-600 text-slate-200"
                onClick={(e) => e.stopPropagation()} />
            </div>
          </CollapsibleSection>
        )}

        {(data.nodeType === 'human-approve' || data.nodeType === 'human-input') && (
          <CollapsibleSection title="Config" defaultOpen>
            <div>
              <label className="text-slate-400 block mb-0.5">Prompt Message</label>
              <textarea value={(config.prompt_message as string) || ''}
                onChange={(e) => updateConfig('prompt_message', e.target.value)}
                placeholder={data.nodeType === 'human-approve' ? 'Please review and approve...' : 'Please provide input...'}
                rows={2}
                className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-slate-200 resize-none text-xs"
                onClick={(e) => e.stopPropagation()} />
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
            </div>
            <div>
              <label className="text-slate-400 block mb-0.5">Skill</label>
              <Input value={(config.skill as string) || ''}
                onChange={(e) => updateConfig('skill', e.target.value)}
                placeholder="summarize"
                className="h-7 bg-slate-700 border-slate-600 text-slate-200"
                onClick={(e) => e.stopPropagation()} />
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

        {agent.startsWith('pattern://') && (
          <PatternConfig
            patternType={agent.replace('pattern://', '')}
            config={config}
            onChange={(newConfig) => {
              Object.entries(newConfig).forEach(([k, v]) => updateConfig(k, v));
            }}
          />
        )}
      </div>

      {showSaved && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 4, padding: "4px", fontSize: 9, color: "#22c55e", borderTop: "1px solid #252528" }}>
          <Check size={9} />
          <span>saved</span>
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className={handleStyle} />

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
