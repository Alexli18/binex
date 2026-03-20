import { Bot, Monitor, ShieldCheck, MessageSquare, Globe, Eye, Terminal, GripVertical } from 'lucide-react';
import { chartColors } from '@/lib/design-tokens';

export interface NodeTypeConfig {
  type: string;
  subtype?: string;
  label: string;
  description: string;
  icon: React.ElementType;
  color: string;
  agentPrefix: string;
  defaultAgent: string;
  category?: string;
}

export const NODE_TYPES: NodeTypeConfig[] = [
  { type: 'llm', label: 'LLM Agent', description: 'Call an LLM model via litellm', icon: Bot, color: '#3b82f6', agentPrefix: 'llm://', defaultAgent: 'llm://openrouter/google/gemma-3-27b-it:free' },
  { type: 'local', label: 'Local Script', description: 'Run a Python function locally', icon: Monitor, color: '#22c55e', agentPrefix: 'local://', defaultAgent: 'local://echo' },
  { type: 'human-approve', subtype: 'approve', label: 'Human Approve', description: 'Pause for human approval', icon: ShieldCheck, color: '#f97316', agentPrefix: 'human://', defaultAgent: 'human://approve' },
  { type: 'human-input', subtype: 'input', label: 'Human Input', description: 'Ask human for free-form input', icon: MessageSquare, color: chartColors.cao, agentPrefix: 'human://', defaultAgent: 'human://input' },
  { type: 'human-output', subtype: 'output', label: 'Human Output', description: 'Display results to the user', icon: Eye, color: '#10b981', agentPrefix: 'human://', defaultAgent: 'human://output' },
  { type: 'a2a', label: 'A2A Agent', description: 'Call a remote A2A agent', icon: Globe, color: '#06b6d4', agentPrefix: 'a2a://', defaultAgent: 'a2a://localhost:8001' },
  { type: 'cao', label: 'CAO Agent', description: 'Run via CLI Agent Orchestrator', icon: Terminal, color: chartColors.cao, agentPrefix: 'cao://', defaultAgent: 'cao://default', category: 'CLI AGENTS' },
];

export function NodePalette() {
  const onDragStart = (event: React.DragEvent, nodeType: NodeTypeConfig) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify(nodeType));
    event.dataTransfer.effectAllowed = 'move';
  };

  const defaultNodes = NODE_TYPES.filter((nt) => !nt.category);
  const cliAgents = NODE_TYPES.filter((nt) => nt.category === 'CLI AGENTS');

  const renderItem = (nt: NodeTypeConfig) => {
    const Icon = nt.icon;
    return (
      <div
        key={nt.type}
        draggable
        onDragStart={(e) => onDragStart(e, nt)}
        className="group/item flex items-start gap-2.5 px-2.5 py-2 rounded-md cursor-grab active:cursor-grabbing hover:bg-slate-800/80 transition-colors border border-transparent hover:border-slate-700/60"
        title={nt.description}
      >
        <div className="w-7 h-7 rounded-md flex items-center justify-center shrink-0 mt-0.5" style={{ backgroundColor: `${nt.color}20` }}>
          <Icon size={15} style={{ color: nt.color }} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-slate-200 leading-tight">{nt.label}</div>
          <div className="text-[10px] text-slate-500 leading-tight mt-0.5">{nt.description}</div>
        </div>
        <GripVertical size={12} className="text-slate-600 opacity-0 group-hover/item:opacity-100 transition-opacity shrink-0 mt-1.5" />
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-0.5 p-2 border-r border-slate-700/60 bg-slate-900 w-52 shrink-0">
      <div className="px-2.5 py-1.5 text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
        Agents
      </div>
      {defaultNodes.map(renderItem)}
      {cliAgents.length > 0 && (
        <>
          <div className="px-2.5 pt-3 py-1.5 text-[10px] font-semibold text-slate-500 uppercase tracking-wider border-t border-slate-700/40 mt-1">
            CLI Agents
          </div>
          {cliAgents.map(renderItem)}
        </>
      )}
    </div>
  );
}
