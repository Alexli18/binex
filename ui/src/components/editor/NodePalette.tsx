import { Bot, Monitor, ShieldCheck, MessageSquare, Globe, Eye } from 'lucide-react';

export interface NodeTypeConfig {
  type: string;
  subtype?: string;
  label: string;
  icon: React.ElementType;
  color: string;
  agentPrefix: string;
  defaultAgent: string;
}

export const NODE_TYPES: NodeTypeConfig[] = [
  { type: 'llm', label: 'LLM Agent', icon: Bot, color: '#3b82f6', agentPrefix: 'llm://', defaultAgent: 'llm://openrouter/gemma-3-27b:free' },
  { type: 'local', label: 'Local Script', icon: Monitor, color: '#22c55e', agentPrefix: 'local://', defaultAgent: 'local://echo' },
  { type: 'human-approve', subtype: 'approve', label: 'Human Approve', icon: ShieldCheck, color: '#f97316', agentPrefix: 'human://', defaultAgent: 'human://approve' },
  { type: 'human-input', subtype: 'input', label: 'Human Input', icon: MessageSquare, color: '#a855f7', agentPrefix: 'human://', defaultAgent: 'human://input' },
  { type: 'human-output', subtype: 'output', label: 'Human Output', icon: Eye, color: '#10b981', agentPrefix: 'human://', defaultAgent: 'human://output' },
  { type: 'a2a', label: 'A2A Agent', icon: Globe, color: '#06b6d4', agentPrefix: 'a2a://', defaultAgent: 'a2a://localhost:8001' },
];

export function NodePalette() {
  const onDragStart = (event: React.DragEvent, nodeType: NodeTypeConfig) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify(nodeType));
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div className="flex flex-col gap-1 p-2 border-r border-slate-700 bg-slate-900 w-48 shrink-0">
      <div className="px-2 py-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider">
        Nodes
      </div>
      {NODE_TYPES.map((nt) => {
        const Icon = nt.icon;
        return (
          <div
            key={nt.type}
            draggable
            onDragStart={(e) => onDragStart(e, nt)}
            className="flex items-center gap-2 px-2 py-2 rounded cursor-grab active:cursor-grabbing hover:bg-slate-800 transition-colors border border-transparent hover:border-slate-700"
            title={`Drag to add ${nt.label}`}
          >
            <Icon size={18} style={{ color: nt.color }} className="shrink-0" />
            <span className="text-sm text-slate-300">{nt.label}</span>
          </div>
        );
      })}
    </div>
  );
}
