import { Bot, Monitor, ShieldCheck, MessageSquare, Globe, Eye, Terminal } from 'lucide-react';
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

// Colors aligned with design-tokens.ts nodeTypeColors
const NODE_COLOR = {
  llm: '#8b5cf6',     // violet-500
  local: '#06b6d4',   // cyan-500
  human: '#f59e0b',   // amber-500
  a2a: '#6366f1',     // indigo-500
  cao: chartColors.cao, // purple-500
} as const;

export const NODE_TYPES: NodeTypeConfig[] = [
  { type: 'llm', label: 'LLM Agent', description: 'Call an LLM model', icon: Bot, color: NODE_COLOR.llm, agentPrefix: 'llm://', defaultAgent: 'llm://openrouter/google/gemma-3-27b-it:free' },
  { type: 'local', label: 'Local Script', description: 'Python function', icon: Monitor, color: NODE_COLOR.local, agentPrefix: 'local://', defaultAgent: 'local://echo' },
  { type: 'human-approve', subtype: 'approve', label: 'Approve', description: 'Human approval gate', icon: ShieldCheck, color: NODE_COLOR.human, agentPrefix: 'human://', defaultAgent: 'human://approve' },
  { type: 'human-input', subtype: 'input', label: 'Human Input', description: 'Free-form input', icon: MessageSquare, color: NODE_COLOR.human, agentPrefix: 'human://', defaultAgent: 'human://input' },
  { type: 'human-output', subtype: 'output', label: 'Output', description: 'Display results', icon: Eye, color: NODE_COLOR.human, agentPrefix: 'human://', defaultAgent: 'human://output' },
  { type: 'a2a', label: 'A2A Agent', description: 'Remote agent', icon: Globe, color: NODE_COLOR.a2a, agentPrefix: 'a2a://', defaultAgent: 'a2a://localhost:8001' },
  { type: 'cao', label: 'CAO Agent', description: 'CLI orchestrator', icon: Terminal, color: NODE_COLOR.cao, agentPrefix: 'cao://', defaultAgent: 'cao://default', category: 'CLI AGENTS' },
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
        className="flex items-center gap-2 px-2 py-1.5 rounded cursor-grab active:cursor-grabbing hover:bg-slate-800/60 transition-colors"
        title={nt.description}
        style={{ borderLeft: `2px solid ${nt.color}` }}
      >
        <Icon size={13} style={{ color: nt.color }} className="shrink-0" />
        <div className="min-w-0 flex-1">
          <span className="text-[12px] text-slate-300">{nt.label}</span>
          <span className="text-[10px] text-slate-600 ml-1.5">{nt.description}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-px p-1.5 border-r border-slate-700/50 bg-slate-900 w-48 shrink-0">
      <div className="px-2 py-1 text-[10px] font-medium text-slate-500 uppercase tracking-wider">
        Agents
      </div>
      {defaultNodes.map(renderItem)}
      {cliAgents.length > 0 && (
        <>
          <div className="px-2 pt-2 py-1 text-[10px] font-medium text-slate-500 uppercase tracking-wider border-t border-slate-700/30 mt-1">
            CLI
          </div>
          {cliAgents.map(renderItem)}
        </>
      )}
      <div className="mt-auto px-2 py-1.5 text-[9px] text-slate-600">
        Drag onto canvas
      </div>
    </div>
  );
}
